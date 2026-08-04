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
from src.rag.documentos import carregar_documento
from src.rag.indice_documental import IndiceDocumental
from src.rag.registro import DocumentoCadastrado, RegistroDocumentos

RAIZ = Path(__file__).resolve().parents[2]
DIRETORIO_CADASTRADOS = RAIZ / "storage" / "documentos"

#: Prefixo que distingue documentos cadastrados em operação dos entregues com o projeto.
#: Aparece nas citações, para que o técnico saiba a procedência da recomendação.
PREFIXO = "DocOp"


class CadastroInvalido(ValueError):
    """Cadastro recusado antes de qualquer processamento."""


@dataclass(frozen=True)
class ResultadoCadastro:
    documento: DocumentoCadastrado
    secoes: list[str]


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


def cadastrar(
    condicao: str,
    arquivo: Path,
    indice: IndiceDocumental,
    registro: RegistroDocumentos,
) -> ResultadoCadastro:
    """Extrai, fatia, indexa e registra um procedimento para a condição informada."""
    canonica = validar_condicao(condicao)
    identificador = _identificador(canonica)

    DIRETORIO_CADASTRADOS.mkdir(parents=True, exist_ok=True)
    destino = DIRETORIO_CADASTRADOS / f"{identificador}.pdf"
    destino.write_bytes(arquivo.read_bytes())

    trechos = carregar_documento(destino, usar_cache=False)
    if not trechos or not any(t.texto.strip() for t in trechos):
        destino.unlink(missing_ok=True)
        raise CadastroInvalido(
            "Não foi possível extrair texto do documento. Verifique se o arquivo é um PDF "
            "legível — digitalizações de baixa qualidade podem não ser reconhecidas."
        )

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
