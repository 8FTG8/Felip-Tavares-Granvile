"""Cadastro de novos procedimentos técnicos em operação (ADR-014).

Fecha o ciclo do guardrail. Quando o sistema recusa um evento por falta de documentação,
ele instrui o técnico a cadastrar o procedimento; este módulo é o que torna essa instrução
verdadeira. O documento cadastrado passa pelo mesmo tratamento da base original —
extração adaptativa, fatiamento por seção, indexação — e o defeito é atendido a partir da
consulta seguinte, sem reinício do serviço.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.ingestion.rotulos import DEFEITOS, ESTADOS, normalizar
from src.rag.documentos import Trecho, extrair_texto, fatiar
from src.rag.indice_documental import IndiceDocumental
from src.rag.mapeamento import cobertura
from src.rag.registro import DocumentoCadastrado, RegistroDocumentos

RAIZ = Path(__file__).resolve().parents[2]
DIRETORIO_CADASTRADOS = RAIZ / "storage" / "documentos"

#: Prefixo que distingue documentos cadastrados em operação dos entregues com o projeto.
#: Aparece nas citações, para que o técnico saiba a procedência da recomendação.
PREFIXO = "DocOp"


class CadastroInvalido(ValueError):
    """Cadastro recusado antes de qualquer processamento."""


class RemocaoInvalida(ValueError):
    """Não há procedimento cadastrado em operação para a condição informada."""


@dataclass(frozen=True)
class ResultadoCadastro:
    documento: DocumentoCadastrado
    secoes: list[str]


@dataclass(frozen=True)
class ResultadoRemocao:
    condicao: str
    documento: str
    trechos: int


def _identificador(condicao: str) -> str:
    limpo = re.sub(r"[^a-z0-9_]", "", condicao.lower())
    return f"{PREFIXO}-{limpo}"


def validar_condicao(condicao: str) -> str:
    """Confere que a condição informada existe na taxonomia e é um defeito.

    Cadastrar procedimento para um estado do sistema não faz sentido — não há falha a
    corrigir —, e aceitar um nome livre criaria uma condição fantasma, jamais alcançada
    por evento algum, já que os rótulos reais passam pela normalização canônica.
    """
    canonica = normalizar(condicao).canonico

    if canonica in ESTADOS:
        raise CadastroInvalido(
            f"'{condicao}' é um estado operacional, não um defeito. "
            "Estados não recebem procedimento de correção."
        )
    if canonica not in DEFEITOS:
        raise CadastroInvalido(
            f"'{condicao}' não corresponde a nenhuma condição conhecida. "
            f"Condições válidas: {', '.join(sorted(DEFEITOS))}."
        )
    return canonica


ILEGIVEL = (
    "Não foi possível extrair texto do documento. Verifique se o arquivo é um PDF "
    "legível — digitalizações de baixa qualidade podem não ser reconhecidas."
)


def _extrair(arquivo: Path, identificador: str) -> list[Trecho]:
    """Lê e fatia o PDF enviado, traduzindo qualquer falha de leitura em recusa.

    A extração acontece a partir do arquivo recebido, e não do destino final: um PDF
    ilegível precisa ser recusado **antes** de qualquer escrita, sob pena de um envio
    inválido apagar o procedimento que já estava cadastrado para a condição.

    Sem a tradução da exceção, um arquivo corrompido subiria como erro não tratado e a
    API responderia 500 — dizendo ao integrador que o serviço tem defeito quando o
    problema está no arquivo que ele mandou. A mensagem abaixo é a que descreve o caso,
    e antes desta função ela era inalcançável: só disparava para PDF válido de texto
    vazio, nunca para o arquivo ilegível que ela descreve.
    """
    try:
        texto, origem = extrair_texto(arquivo, usar_cache=False)
    except Exception as erro:  # noqa: BLE001 — qualquer falha de leitura é o mesmo caso
        raise CadastroInvalido(ILEGIVEL) from erro

    trechos = fatiar(texto, documento=identificador, origem=origem)
    if not trechos or not any(t.texto.strip() for t in trechos):
        raise CadastroInvalido(ILEGIVEL)
    return trechos


def cadastrar(
    condicao: str,
    arquivo: Path,
    indice: IndiceDocumental,
    registro: RegistroDocumentos,
) -> ResultadoCadastro:
    """Extrai, fatia, indexa e registra um procedimento para a condição informada.

    A ordem dos passos é a garantia de que um cadastro inválido não danifica o anterior:
    valida-se o arquivo enviado antes de tocar em qualquer estado, e só então grava-se o
    PDF, poda-se o índice e registra-se a associação.
    """
    canonica = validar_condicao(condicao)
    identificador = _identificador(canonica)
    trechos = _extrair(arquivo, identificador)

    DIRETORIO_CADASTRADOS.mkdir(parents=True, exist_ok=True)
    destino = DIRETORIO_CADASTRADOS / f"{identificador}.pdf"
    destino.write_bytes(arquivo.read_bytes())

    # Poda antes de indexar: o upsert atualiza os ids recebidos e não apaga os ausentes,
    # de modo que um procedimento com menos seções que o anterior deixaria as excedentes
    # recuperáveis — citadas como fonte de um documento que já foi substituído.
    indice.remover_documento(identificador)
    indice.indexar(tuple(trechos))

    cadastrado = registro.registrar(
        condicao=canonica,
        documento=identificador,
        arquivo=str(destino),
        trechos=len(trechos),
        origem=trechos[0].origem,
    )

    return ResultadoCadastro(
        documento=cadastrado,
        secoes=[f"{t.numero_secao}. {t.titulo_secao}" for t in trechos],
    )


def _motivo_da_recusa(canonica: str) -> str:
    """Explica por que não há o que remover, separando os dois casos.

    Uma condição coberta pelo mapa versionado *tem* documento, e responder o mesmo texto
    de uma condição nunca cadastrada faria o integrador concluir que ela não existe.
    """
    estatica = cobertura(canonica)
    if estatica.documentada:
        return (
            f"'{canonica}' é atendida por {estatica.documento}, da base entregue com o "
            "projeto. Essa cobertura é versionada em código e não se altera pela API — "
            "só o que foi cadastrado em operação pode ser removido."
        )
    return f"Não há procedimento cadastrado em operação para '{canonica}'."


def remover(
    condicao: str,
    indice: IndiceDocumental,
    registro: RegistroDocumentos,
) -> ResultadoRemocao:
    """Desfaz um cadastro feito em operação, devolvendo a condição à recusa.

    Só alcança o que foi cadastrado em operação. A cobertura declarada em
    `src/rag/mapeamento.py` é afirmação de projeto, versionada e coberta por teste — é dela
    que sai a recusa de `eccentric_rotor` do ADR-011 —, e uma rota HTTP não apaga uma linha
    de código. Para essas condições a remoção não se aplica, e o chamador recebe a recusa.

    A ordem inverte a do cadastro e poda o índice primeiro. Se a operação for interrompida
    no meio, sobra uma condição que consta como coberta e não recupera trecho algum — um
    defeito visível na consulta seguinte. A ordem oposta deixaria trechos recuperáveis de
    um documento que o registro já não conhece, citáveis como fonte legítima, que é
    exatamente o modo de falha que o ADR-004 existe para impedir.
    """
    canonica = validar_condicao(condicao)
    alvo = registro.buscar(canonica)
    if alvo is None:
        raise RemocaoInvalida(_motivo_da_recusa(canonica))

    trechos = indice.remover_documento(alvo.documento)
    registro.remover(canonica)
    Path(alvo.arquivo).unlink(missing_ok=True)

    return ResultadoRemocao(condicao=canonica, documento=alvo.documento, trechos=trechos)
