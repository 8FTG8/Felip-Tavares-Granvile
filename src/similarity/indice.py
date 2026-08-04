"""Busca por ocorrências históricas semelhantes (ADR-003, ADR-007, ADR-008).

Dado um evento novo, o índice localiza os registros históricos com comportamento mais
próximo e devolve o contexto que o enunciado pede: quantidade de eventos similares,
distribuição ao longo do tempo, frequência de ocorrência e contexto operacional.

Três decisões moldam a implementação:

**Busca global** (ADR-008). A vizinhança percorre todo o histórico, sem filtrar pelo
rótulo do evento de entrada, e cada vizinho é apresentado com sua família de defeito.
Restringir a busca ao próprio rótulo tornaria o resultado circular. Como efeito
colateral valioso, a busca global evidencia que os vizinhos de um `rolamento_inner` são
majoritariamente de outras famílias de rolamento — a demonstração visual do que o
ADR-003 sustenta com números.

**Deduplicação assimétrica** (ADR-007). O índice guarda vetores de atributos distintos,
para que os *k* vizinhos sejam de fato *k* leituras diferentes e não a mesma medição
repetida. Já as contagens apresentadas ao usuário usam o histórico completo, porque a
frequência real de ocorrência é a verdade operacional que interessa à manutenção.

**Sem classificação** (ADR-003). O índice não prediz o defeito: o rótulo vem anotado pelo
operador no próprio evento de entrada. A vizinhança serve para contextualizar, não para
decidir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from src.ingestion.eventos import ATRIBUTOS, SATURACAO_KURTOSIS, carregar_eventos
from src.ingestion.rotulos import normalizar

VIZINHOS_PADRAO = 10


@dataclass(frozen=True)
class Vizinho:
    """Uma ocorrência histórica semelhante ao evento consultado."""

    id: int
    created_at: pd.Timestamp
    condicao: str
    tipo_condicao: str
    rotulo_bruto: str
    rpm: float
    distancia: float
    similaridade: float
    leituras_identicas: int
    """Quantas leituras do histórico compartilham exatamente este vetor de atributos."""


@dataclass(frozen=True)
class OcorrenciasPorCondicao:
    """Resumo do histórico de uma condição presente na vizinhança."""

    condicao: str
    tipo_condicao: str
    vizinhos: int
    """Quantos dos k vizinhos retornados pertencem a esta condição."""
    ocorrencias_historicas: int
    """Total de eventos desta condição no histórico completo."""
    primeira: pd.Timestamp
    ultima: pd.Timestamp
    dias_com_registro: int
    frequencia_diaria: float
    """Média de eventos por dia com registro — a frequência pedida pelo enunciado."""


@dataclass(frozen=True)
class ContextoSimilaridade:
    """Resposta completa da busca por similaridade para um evento."""

    condicao_informada: str
    tipo_condicao_informada: str
    rotulo_bruto: str
    vizinhos: list[Vizinho]
    ocorrencias: list[OcorrenciasPorCondicao]
    distribuicao_temporal: pd.Series
    """Contagem de eventos por dia, considerando as condições presentes na vizinhança."""
    contexto_operacional: dict[str, float] = field(default_factory=dict)

    @property
    def condicao_predominante(self) -> str:
        """Condição mais frequente entre os vizinhos — informativa, nunca decisória."""
        return self.ocorrencias[0].condicao if self.ocorrencias else "desconhecido"

    @property
    def total_ocorrencias_similares(self) -> int:
        return sum(o.ocorrencias_historicas for o in self.ocorrencias)


class IndiceSimilaridade:
    """Índice k-NN sobre os atributos de vibração, padronizados.

    A padronização é obrigatória: os atributos vivem em escalas incompatíveis — `rpm`
    varia de 0 a 3000, `z_rms_acceleration_g` fica abaixo de 4. Sem padronizar, a
    distância euclidiana seria essencialmente a diferença de rotação.
    """

    def __init__(self, eventos: pd.DataFrame, vizinhos: int = VIZINHOS_PADRAO) -> None:
        self._eventos = eventos.reset_index(drop=True)
        self._k = vizinhos
        self._preparar()

    @classmethod
    def a_partir_do_arquivo(cls, caminho=None, vizinhos: int = VIZINHOS_PADRAO) -> "IndiceSimilaridade":
        return cls(carregar_eventos(caminho), vizinhos=vizinhos)

    # -- construção ----------------------------------------------------------------

    def _preparar(self) -> None:
        self._tetos = self._calcular_tetos(self._eventos[list(ATRIBUTOS)])
        atributos = self._tratar_saturacao(self._eventos[list(ATRIBUTOS)])

        # Um representante por vetor distinto, guardando a multiplicidade para que as
        # contagens sigam refletindo o histórico completo (ADR-007).
        chave = atributos.round(6)
        primeiro = ~chave.duplicated()
        grupo = chave.groupby(list(chave.columns), sort=False).ngroup()
        multiplicidade = grupo.map(grupo.value_counts())

        self._representantes = self._eventos.loc[primeiro].copy()
        self._representantes["leituras_identicas"] = multiplicidade.loc[primeiro].astype(int)

        self._escalador = StandardScaler().fit(atributos.loc[primeiro])
        matriz = self._escalador.transform(atributos.loc[primeiro])

        self._knn = NearestNeighbors(n_neighbors=self._k, metric="euclidean")
        self._knn.fit(matriz)

        # Estatísticas históricas sobre o conjunto completo, não sobre os representantes.
        self._historico = self._resumir_historico(self._eventos)

    @staticmethod
    def _calcular_tetos(atributos: pd.DataFrame) -> dict[str, float]:
        """Maior curtose legítima observada no histórico, por eixo.

        O teto é aprendido uma única vez, na construção do índice, e reutilizado nas
        consultas. Recalculá-lo a cada consulta seria incorreto: um evento isolado com
        leitura saturada não tem valor não saturado algum de onde extrair o limite.
        """
        tetos: dict[str, float] = {}
        for coluna in ("z_kurtosis", "x_kurtosis"):
            if coluna not in atributos:
                continue
            legitimos = atributos.loc[atributos[coluna] < SATURACAO_KURTOSIS, coluna]
            tetos[coluna] = float(legitimos.max()) if not legitimos.empty else SATURACAO_KURTOSIS
        return tetos

    def _tratar_saturacao(self, atributos: pd.DataFrame) -> pd.DataFrame:
        """Censura as leituras de curtose que estouraram o registrador uint16.

        O valor 65,535 (= 2¹⁶ − 1) não é uma medição: é o teto do registrador. Mantê-lo
        cru criaria vizinhanças artificiais entre eventos cujo único traço comum é ter
        saturado o sensor. Substitui-se pelo maior valor legítimo do histórico.
        """
        tratados = atributos.copy()
        for coluna, teto in self._tetos.items():
            if coluna in tratados:
                tratados.loc[tratados[coluna] >= SATURACAO_KURTOSIS, coluna] = teto
        return tratados

    @staticmethod
    def _resumir_historico(eventos: pd.DataFrame) -> dict[str, dict]:
        resumo: dict[str, dict] = {}
        for condicao, grupo in eventos.groupby("condicao"):
            dias = grupo["created_at"].dt.normalize().nunique()
            resumo[condicao] = {
                "tipo_condicao": grupo["tipo_condicao"].iloc[0],
                "ocorrencias": len(grupo),
                "primeira": grupo["created_at"].min(),
                "ultima": grupo["created_at"].max(),
                "dias_com_registro": int(dias),
                "frequencia_diaria": len(grupo) / dias if dias else 0.0,
            }
        return resumo

    # -- consulta ------------------------------------------------------------------

    def consultar(
        self, evento: dict, vizinhos: int | None = None, excluir_proprio: bool = True
    ) -> ContextoSimilaridade:
        """Localiza as ocorrências históricas mais semelhantes ao evento informado.

        ``evento`` é o JSON de entrada descrito no enunciado. Atributos ausentes são
        rejeitados: uma leitura incompleta produziria vizinhança sem significado.

        Com ``excluir_proprio``, um evento que já conste do histórico não é devolvido
        como sua própria ocorrência semelhante — o que ocorre ao reprocessar um registro
        existente, inclusive com o exemplo do enunciado, que corresponde ao ``id``
        114387 do conjunto.
        """
        k = vizinhos or self._k
        faltantes = [a for a in ATRIBUTOS if a not in evento]
        if faltantes:
            raise ValueError(f"Atributos ausentes no evento: {', '.join(faltantes)}")

        proprio = evento.get("id") if excluir_proprio else None
        buscar = min(k + (1 if proprio is not None else 0), len(self._representantes))

        consulta = pd.DataFrame([{a: float(evento[a]) for a in ATRIBUTOS}])
        consulta = self._tratar_saturacao(consulta)
        distancias, posicoes = self._knn.kneighbors(
            self._escalador.transform(consulta), n_neighbors=buscar
        )

        encontrados = self._representantes.iloc[posicoes[0]]
        if proprio is not None:
            manter = encontrados["id"].to_numpy() != proprio
            encontrados, distancias = encontrados[manter], distancias[0][manter].reshape(1, -1)
        encontrados, distancias = encontrados.iloc[:k], distancias[:, :k]
        lista = [
            Vizinho(
                id=int(linha.id),
                created_at=linha.created_at,
                condicao=linha.condicao,
                tipo_condicao=linha.tipo_condicao,
                rotulo_bruto=linha.fault,
                rpm=float(linha.rpm),
                distancia=float(distancia),
                similaridade=1.0 / (1.0 + float(distancia)),
                leituras_identicas=int(linha.leituras_identicas),
            )
            for linha, distancia in zip(encontrados.itertuples(), distancias[0])
        ]

        condicao = normalizar(evento.get("fault"))
        return ContextoSimilaridade(
            condicao_informada=condicao.canonico,
            tipo_condicao_informada=condicao.tipo.value,
            rotulo_bruto=condicao.bruto,
            vizinhos=lista,
            ocorrencias=self._agregar(lista),
            distribuicao_temporal=self._distribuir_no_tempo(lista),
            contexto_operacional=self._contexto_operacional(lista),
        )

    def _agregar(self, vizinhos: list[Vizinho]) -> list[OcorrenciasPorCondicao]:
        contagem: dict[str, int] = {}
        for vizinho in vizinhos:
            contagem[vizinho.condicao] = contagem.get(vizinho.condicao, 0) + 1

        agregado = [
            OcorrenciasPorCondicao(
                condicao=condicao,
                tipo_condicao=self._historico[condicao]["tipo_condicao"],
                vizinhos=quantos,
                ocorrencias_historicas=self._historico[condicao]["ocorrencias"],
                primeira=self._historico[condicao]["primeira"],
                ultima=self._historico[condicao]["ultima"],
                dias_com_registro=self._historico[condicao]["dias_com_registro"],
                frequencia_diaria=self._historico[condicao]["frequencia_diaria"],
            )
            for condicao, quantos in contagem.items()
        ]
        return sorted(agregado, key=lambda o: (-o.vizinhos, -o.ocorrencias_historicas))

    def _distribuir_no_tempo(self, vizinhos: list[Vizinho]) -> pd.Series:
        condicoes = {v.condicao for v in vizinhos}
        recorte = self._eventos[self._eventos["condicao"].isin(condicoes)]
        serie = recorte.groupby(recorte["created_at"].dt.normalize()).size()
        serie.name = "eventos"
        serie.index.name = "dia"
        return serie

    def _contexto_operacional(self, vizinhos: list[Vizinho]) -> dict[str, float]:
        if not vizinhos:
            return {}
        rotacoes = np.array([v.rpm for v in vizinhos])
        return {
            "rpm_predominante": float(pd.Series(rotacoes).mode().iloc[0]),
            "rpm_medio": float(rotacoes.mean()),
            "similaridade_maxima": max(v.similaridade for v in vizinhos),
            "similaridade_media": float(np.mean([v.similaridade for v in vizinhos])),
        }

    # -- introspecção --------------------------------------------------------------

    @property
    def total_eventos(self) -> int:
        return len(self._eventos)

    @property
    def total_representantes(self) -> int:
        """Vetores distintos indexados — menor que o total por conta da deduplicação."""
        return len(self._representantes)

    def __repr__(self) -> str:
        return (
            f"IndiceSimilaridade({self.total_representantes:,} vetores distintos "
            f"de {self.total_eventos:,} eventos, k={self._k})"
        )
