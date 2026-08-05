"""Geração da recomendação prescritiva (ADR-001, ADR-004).

O modelo de linguagem entra aqui, e apenas aqui. Ele nunca decide *se* responde — isso é
atribuição do roteador, que é determinístico — e recebe exclusivamente os trechos que
sobreviveram às duas barreiras. Seu trabalho é redigir, em português técnico, o que os
procedimentos já dizem.

O desenho parte de uma premissa: um modelo de 7B não sabe manutenção industrial e não
precisa saber. Toda a competência técnica da resposta vem dos trechos recuperados. Isso é
o que torna aceitável rodar um modelo pequeno em estação comercial — e é também o que
mantém a resposta auditável, já que cada afirmação tem uma seção de procedimento por trás.

As respostas dos caminhos de recusa não passam pelo modelo. São compostas em código, a
partir da justificativa registrada no mapa de cobertura. Um texto de recusa gerado por LLM
poderia, ele próprio, alucinar uma explicação técnica para a ausência do documento.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass

import ollama

from src.rag.roteador import LIMIAR_RELEVANCIA, Caminho, Decisao

#: Modelo de produção, dimensionado para a estação de trabalho descrita no enunciado —
#: 32 GB de RAM e GPU de 16 GB. Quantizado, ocupa cerca de 5 GB de VRAM.
MODELO_PRODUCAO = "qwen2.5:7b-instruct"

#: Modelo alternativo para hardware sem GPU dedicada (ADR-013). A mesma arquitetura de
#: RAG opera com qualquer um dos dois: como toda a competência técnica vem dos trechos
#: recuperados, o modelo menor perde fluência de redação, não conteúdo.
MODELO_REDUZIDO = "qwen2.5:3b-instruct"

#: Selecionado por ``MODELO_LLM``. Sem a variável, usa o modelo de produção.
MODELO = os.getenv("MODELO_LLM", MODELO_PRODUCAO)

#: Temperatura baixa: a tarefa é reescrever procedimento técnico, não criar texto. Valores
#: mais altos aumentam a chance de o modelo introduzir passos que não estão nos trechos.
TEMPERATURA = 0.2

#: Teto de geração. Suficiente para um procedimento completo com passos numerados.
MAXIMO_TOKENS = 800

INSTRUCAO_SISTEMA = """\
Você é um assistente técnico de manutenção industrial. Sua função é orientar equipes de \
campo sobre como corrigir falhas em máquinas rotativas.

Regras obrigatórias:

1. Responda EXCLUSIVAMENTE com base nos trechos de procedimento fornecidos. Você não tem \
conhecimento próprio sobre o equipamento desta planta.
2. Se os trechos não contiverem a informação necessária, diga explicitamente que o \
procedimento disponível não cobre aquele ponto. Nunca complete a lacuna com conhecimento \
geral.
3. Cite a fonte de cada orientação no formato (Documento, seção N).
4. Não invente valores numéricos, torques, tolerâncias, frequências ou intervalos que não \
estejam nos trechos.
5. Escreva em português do Brasil, de forma direta e operacional, em passos numerados \
quando o procedimento for sequencial.
6. Comece pela ação mais urgente do ponto de vista de segurança, quando os trechos a \
mencionarem."""


@dataclass(frozen=True)
class Recomendacao:
    """Resposta final entregue ao usuário."""

    texto: str
    caminho: Caminho
    condicao: str
    citacoes: list[str]
    modelo: str | None
    """``None`` quando a resposta foi composta sem acionar o modelo de linguagem."""

    @property
    def gerada_por_llm(self) -> bool:
        return self.modelo is not None


def _contexto(decisao: Decisao) -> str:
    """Monta o contexto do prompt, um bloco por trecho, com a fonte no cabeçalho."""
    blocos = []
    for recuperado in decisao.trechos:
        trecho = recuperado.trecho
        blocos.append(
            f"[{trecho.documento}, seção {trecho.numero_secao} — {trecho.titulo_secao}]\n"
            f"{trecho.texto}"
        )
    return "\n\n---\n\n".join(blocos)


def _prompt(decisao: Decisao, pergunta: str | None) -> str:
    condicao = decisao.condicao.replace("_", " ")
    solicitacao = pergunta or (
        f"Um novo evento foi registrado com a condição '{condicao}'. "
        "Explique como diagnosticar e corrigir esse problema."
    )
    return (
        f"Trechos do procedimento técnico aplicável:\n\n{_contexto(decisao)}\n\n"
        f"---\n\nSolicitação: {solicitacao}"
    )


def _resposta_estado(decisao: Decisao) -> str:
    condicao = decisao.condicao.replace("_", " ")
    return (
        f"**Nenhum defeito detectado.** O evento registra o estado operacional "
        f"*{condicao}*, que não representa uma falha.\n\n"
        f"{decisao.cobertura.justificativa}\n\n"
        "Não há ação corretiva a recomendar. O contexto estatístico do evento continua "
        "disponível para acompanhamento da condição do equipamento."
    )


def _resposta_sem_documento(decisao: Decisao) -> str:
    condicao = decisao.condicao.replace("_", " ")
    corpo = [
        f"**Não há procedimento técnico cadastrado para *{condicao}*.**",
        "",
        decisao.cobertura.justificativa,
        "",
        "Por esse motivo, o sistema não emite recomendação de correção para este evento: "
        "prescrever uma intervenção sem respaldo documental poderia levar a ação no "
        "componente errado.",
        "",
        "**O que fazer:** registre um documento com o procedimento de diagnóstico e "
        f"correção para *{condicao}*. Assim que o documento for cadastrado, este tipo de "
        "evento passa a receber recomendação automaticamente.",
    ]
    if decisao.relevancia_maxima is not None:
        corpo.extend(
            [
                "",
                f"*O procedimento roteado ({decisao.documento}) foi consultado, mas nenhuma "
                f"de suas seções responde a esta solicitação com relevância suficiente "
                f"(máxima observada: {decisao.relevancia_maxima:.3f}; mínima exigida: "
                f"{LIMIAR_RELEVANCIA:.3f}).*",
            ]
        )
    return "\n".join(corpo)


class ModeloIndisponivel(RuntimeError):
    """O serviço de modelos não pôde atender à geração.

    É condição **prevista** de operação, não defeito: o Ollama pode não ter subido, ou o
    modelo configurado pode não estar baixado naquela máquina. Existe como exceção
    própria para que a API a traduza em 503 — e não no 500 genérico, que diz ao
    integrador que o serviço está com bug quando ele só está sem modelo.

    Atinge unicamente o caminho de prescrição. Os dois caminhos de recusa e o de estado
    seguem respondendo com o modelo fora do ar, porque seus textos são compostos em
    código: é a arquitetura do ADR-004 se sustentando sozinha sob falha.
    """


class Gerador:
    """Produz a recomendação a partir da decisão do roteador."""

    def __init__(self, modelo: str = MODELO, cliente: ollama.Client | None = None) -> None:
        self._modelo = modelo
        self._cliente = cliente or ollama.Client()

    def responder(
        self,
        decisao: Decisao,
        pergunta: str | None = None,
        historico: list[dict[str, str]] | None = None,
    ) -> Recomendacao:
        """Compõe a resposta do caminho decidido pelo roteador.

        Os caminhos de recusa não acionam o modelo: seu texto é determinístico, montado a
        partir da justificativa registrada no mapa de cobertura.
        """
        if decisao.caminho is Caminho.ESTADO:
            return Recomendacao(
                texto=_resposta_estado(decisao),
                caminho=decisao.caminho,
                condicao=decisao.condicao,
                citacoes=[],
                modelo=None,
            )

        if decisao.caminho is Caminho.SEM_DOCUMENTO:
            return Recomendacao(
                texto=_resposta_sem_documento(decisao),
                caminho=decisao.caminho,
                condicao=decisao.condicao,
                citacoes=[],
                modelo=None,
            )

        try:
            resposta = self._cliente.chat(
                model=self._modelo,
                messages=self._mensagens(decisao, pergunta, historico),
                options={"temperature": TEMPERATURA, "num_predict": MAXIMO_TOKENS},
            )
        except Exception as erro:  # noqa: BLE001 — traduzido logo abaixo
            raise self._indisponivel(erro) from erro

        return Recomendacao(
            texto=resposta["message"]["content"].strip(),
            caminho=decisao.caminho,
            condicao=decisao.condicao,
            citacoes=decisao.citacoes,
            modelo=self._modelo,
        )

    def responder_em_fluxo(
        self,
        decisao: Decisao,
        pergunta: str | None = None,
        historico: list[dict[str, str]] | None = None,
    ) -> Iterator[str]:
        """Versão incremental de :meth:`responder`, para a interface de chat.

        Em hardware sem GPU dedicada a geração leva dezenas de segundos, e ver o texto
        surgindo torna a espera aceitável. Os caminhos de recusa continuam instantâneos e
        são emitidos de uma vez.

        **Não é uma função geradora**, e isso é deliberado. Se fosse, nada aqui rodaria
        até o primeiro ``next()`` — que, na API, acontece depois de os cabeçalhos da
        resposta já terem sido enviados, quando devolver 503 já é impossível. Sendo uma
        função comum que *retorna* um gerador, a verificação abaixo executa na chamada, a
        tempo de a API traduzir a falha em status.
        """
        if not decisao.deve_gerar:
            return iter([self.responder(decisao, pergunta).texto])

        self.verificar()

        def partes() -> Iterator[str]:
            try:
                for parte in self._cliente.chat(
                    model=self._modelo,
                    messages=self._mensagens(decisao, pergunta, historico),
                    options={"temperature": TEMPERATURA, "num_predict": MAXIMO_TOKENS},
                    stream=True,
                ):
                    yield parte["message"]["content"]
            except Exception as erro:  # noqa: BLE001 — traduzido logo abaixo
                # Cair no meio da transmissão não permite mais trocar o status; a exceção
                # sobe e o cliente trata o fluxo interrompido.
                raise self._indisponivel(erro) from erro

        return partes()

    def _mensagens(
        self,
        decisao: Decisao,
        pergunta: str | None,
        historico: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        """Monta a conversa enviada ao modelo.

        O histórico dá continuidade ao diálogo — "e se o eixo estiver empenado?" só faz
        sentido depois da pergunta anterior. Os trechos recuperados, porém, são sempre os
        da **rodada atual**: o contexto documental é reconstruído a cada pergunta, de modo
        que o modelo nunca responda apoiado em trechos de um turno anterior que já não
        foram recuperados. Sem isso, a citação deixaria de corresponder ao que sustenta a
        resposta.
        """
        mensagens = [{"role": "system", "content": INSTRUCAO_SISTEMA}]
        for turno in historico or []:
            if turno.get("papel") in {"usuario", "assistente"} and turno.get("conteudo"):
                papel = "user" if turno["papel"] == "usuario" else "assistant"
                mensagens.append({"role": papel, "content": turno["conteudo"]})
        mensagens.append({"role": "user", "content": _prompt(decisao, pergunta)})
        return mensagens

    @property
    def modelo(self) -> str:
        """Modelo em uso, exibido na interface para que a demonstração seja explícita."""
        return self._modelo

    def verificar(self) -> None:
        """Confere se o modelo pode atender, levantando :class:`ModeloIndisponivel`.

        Distingue os dois motivos, porque a ação corretiva é diferente: subir o serviço
        ou baixar o modelo. Uma mensagem genérica mandaria conferir a coisa errada.
        """
        try:
            catalogo = self._cliente.list().get("models", [])
        except Exception as erro:  # noqa: BLE001 — traduzido logo abaixo
            raise ModeloIndisponivel(
                "O serviço de modelos (Ollama) não está respondendo. "
                "Inicie-o com `ollama serve` e tente novamente."
            ) from erro

        familia = self._modelo.split(":")[0]
        if not any(m.get("model", "").startswith(familia) for m in catalogo):
            raise ModeloIndisponivel(
                f"O modelo {self._modelo} não está instalado nesta máquina. "
                f"Baixe-o com `ollama pull {self._modelo}`."
            )

    def disponivel(self) -> bool:
        """Forma booleana de :meth:`verificar`, publicada em ``GET /sistema``."""
        try:
            self.verificar()
            return True
        except ModeloIndisponivel:
            return False

    def _indisponivel(self, erro: Exception) -> ModeloIndisponivel:
        """Traduz a falha do cliente, consultando o serviço para dar o motivo exato."""
        if isinstance(erro, ModeloIndisponivel):
            return erro
        try:
            self.verificar()
        except ModeloIndisponivel as diagnostico:
            return diagnostico
        # O serviço responde e o modelo existe: a falha é outra, e a mensagem genérica
        # é honesta em vez de inventar um diagnóstico.
        return ModeloIndisponivel(f"Falha ao gerar a resposta com {self._modelo}: {erro}")
