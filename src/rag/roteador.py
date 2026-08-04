"""Roteamento das respostas e barreiras contra alucinação (ADR-004, ADR-006, ADR-010).

Este módulo decide **se** o sistema responde, antes de qualquer geração de texto. A
decisão é inteiramente determinística: nenhum dos caminhos depende do modelo de
linguagem para ser escolhido, e o modelo só é acionado no caminho em que há respaldo
documental para citar.

Os três caminhos (ADR-006):

``ESTADO``
    O evento registra um estado operacional — ``normal``, ``motor_desligado``,
    ``teste``, ``baseline``, ``acelerando``. Não há falha a corrigir. Um sistema com
    apenas dois caminhos responderia "não existe documento para o defeito `normal`",
    afirmando que `normal` é um defeito e contradizendo o enunciado.

``SEM_DOCUMENTO``
    Defeito real, sem procedimento técnico que o cubra. O sistema recusa a prescrição,
    explica o motivo e convida ao cadastro do documento.

``PRESCRICAO``
    Defeito coberto por documento e com trechos relevantes recuperados. Único caminho em
    que o modelo de linguagem é chamado, e ainda assim restrito aos trechos citados.

As duas barreiras operam em sequência. A primeira é o mapa defeito → documento: consulta
a dicionário, impossível de contornar por formulação de pergunta. A segunda é o limiar de
relevância sobre os trechos recuperados, que cobre o caso de existir documento para o
defeito sem que nenhuma seção responda à pergunta específica do técnico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.ingestion.rotulos import TipoCondicao, normalizar
from src.rag.indice_documental import IndiceDocumental, TrechoRecuperado
from src.rag.mapeamento import Cobertura, cobertura
from src.rag.registro import RegistroDocumentos

#: Limiar de relevância da segunda barreira, calibrado por ``scripts/calibrar_limiar.py``
#: contra 30 perguntas — 16 respondidas pelo documento roteado e 14 sobre assuntos
#: ausentes dele (ADR-010). As duas distribuições não se sobrepõem: as pertinentes ficam
#: entre 0,8728 e 0,9261; as impertinentes, entre 0,7858 e 0,8409. O corte é o ponto de
#: margem máxima nesse vão, separando 16/16 e 14/14.
LIMIAR_RELEVANCIA = 0.8569

TRECHOS_PADRAO = 4


class Caminho(str, Enum):
    ESTADO = "estado"
    SEM_DOCUMENTO = "sem_documento"
    PRESCRICAO = "prescricao"


class MotivoRecusa(str, Enum):
    """Por que a prescrição não foi produzida. Registrado para auditoria."""

    NAO_E_DEFEITO = "nao_e_defeito"
    DEFEITO_SEM_DOCUMENTO = "defeito_sem_documento"
    CONDICAO_DESCONHECIDA = "condicao_desconhecida"
    SEM_TRECHO_RELEVANTE = "sem_trecho_relevante"


@dataclass(frozen=True)
class Decisao:
    """Resultado do roteamento, anterior a qualquer geração de texto."""

    caminho: Caminho
    condicao: str
    tipo_condicao: str
    rotulo_bruto: str
    cobertura: Cobertura
    trechos: list[TrechoRecuperado] = field(default_factory=list)
    motivo: MotivoRecusa | None = None
    relevancia_maxima: float | None = None

    @property
    def deve_gerar(self) -> bool:
        """Se o modelo de linguagem pode ser acionado."""
        return self.caminho is Caminho.PRESCRICAO

    @property
    def documento(self) -> str | None:
        return self.cobertura.documento

    @property
    def citacoes(self) -> list[str]:
        return [t.citacao for t in self.trechos]


class Roteador:
    """Aplica as barreiras e decide o caminho de resposta de cada evento."""

    def __init__(
        self,
        indice: IndiceDocumental,
        limiar: float = LIMIAR_RELEVANCIA,
        trechos: int = TRECHOS_PADRAO,
        registro: RegistroDocumentos | None = None,
    ) -> None:
        self._indice = indice
        self._limiar = limiar
        self._trechos = trechos
        self._registro = registro

    def _cobertura(self, condicao: str) -> Cobertura:
        """Cobertura documental da condição, considerando cadastros feitos em operação.

        O mapa estático descreve a base entregue com o projeto; o registro acrescenta os
        procedimentos cadastrados depois, em resposta às próprias recusas do sistema
        (ADR-014). A ordem importa: um cadastro em operação sobrepõe-se ao mapa, porque
        representa conhecimento mais recente da equipe de manutenção.
        """
        situacao = cobertura(condicao)
        if situacao.documentada or self._registro is None:
            return situacao

        cadastrado = self._registro.documento_de(condicao)
        if cadastrado is None:
            return situacao

        return Cobertura(condicao=condicao, documento=cadastrado, justificativa="")

    def decidir(self, rotulo: str | None, pergunta: str | None = None) -> Decisao:
        """Decide o caminho para um evento, sem acionar o modelo de linguagem.

        ``pergunta`` é a consulta do técnico. Ausente, usa-se uma formulação padrão
        derivada da condição — o caso do evento que chega automaticamente do sensor, sem
        ninguém tendo perguntado nada.
        """
        condicao = normalizar(rotulo)
        situacao = self._cobertura(condicao.canonico)

        base = {
            "condicao": condicao.canonico,
            "tipo_condicao": condicao.tipo.value,
            "rotulo_bruto": condicao.bruto,
            "cobertura": situacao,
        }

        # Estado do sistema: não há falha a corrigir (ADR-006).
        if condicao.tipo is TipoCondicao.ESTADO:
            return Decisao(caminho=Caminho.ESTADO, motivo=MotivoRecusa.NAO_E_DEFEITO, **base)

        # Primeira barreira: mapa defeito → documento (ADR-010).
        if not situacao.documentada:
            motivo = (
                MotivoRecusa.CONDICAO_DESCONHECIDA
                if condicao.tipo is TipoCondicao.DESCONHECIDO
                else MotivoRecusa.DEFEITO_SEM_DOCUMENTO
            )
            return Decisao(caminho=Caminho.SEM_DOCUMENTO, motivo=motivo, **base)

        # Segunda barreira: relevância dos trechos recuperados (ADR-010).
        recuperados = self._indice.buscar(
            pergunta or self._pergunta_padrao(condicao.canonico),
            documento=situacao.documento,
            trechos=self._trechos,
        )
        relevantes = [t for t in recuperados if t.relevancia >= self._limiar]

        if not relevantes:
            return Decisao(
                caminho=Caminho.SEM_DOCUMENTO,
                motivo=MotivoRecusa.SEM_TRECHO_RELEVANTE,
                relevancia_maxima=max((t.relevancia for t in recuperados), default=None),
                **base,
            )

        return Decisao(
            caminho=Caminho.PRESCRICAO,
            trechos=relevantes,
            relevancia_maxima=relevantes[0].relevancia,
            **base,
        )

    @staticmethod
    def _pergunta_padrao(condicao: str) -> str:
        """Consulta usada quando o evento chega do sensor, sem pergunta do técnico."""
        legivel = condicao.replace("_", " ")
        return f"como diagnosticar e corrigir o problema de {legivel}"

    @property
    def limiar(self) -> float:
        return self._limiar
