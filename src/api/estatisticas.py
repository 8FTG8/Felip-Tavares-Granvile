"""Agregações do histórico para o painel (ADR-002).

Os números vêm do mesmo conjunto que alimenta a busca por similaridade, e são calculados
sobre o histórico completo — não sobre os representantes deduplicados do índice. A
distinção importa: o painel responde "com que frequência isto acontece na fábrica", e a
resposta é a contagem de eventos reais, não a de leituras distintas.

As agregações são calculadas uma única vez, na construção, porque o histórico é imutável
em operação: novos eventos chegam pela API e são analisados, mas o conjunto de referência
só muda com nova carga.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.ingestion.rotulos import DEFEITOS, ESTADOS


@dataclass(frozen=True)
class ResumoGeral:
    total_eventos: int
    total_defeitos: int
    total_estados: int
    familias_de_defeito: int
    primeiro_evento: pd.Timestamp
    ultimo_evento: pd.Timestamp
    dias_com_registro: int


@dataclass(frozen=True)
class ContagemCondicao:
    condicao: str
    tipo_condicao: str
    eventos: int
    proporcao: float
    primeira: pd.Timestamp
    ultima: pd.Timestamp
    dias_com_registro: int
    frequencia_diaria: float
    rotulos_brutos: int
    """Quantas grafias distintas o operador usou para esta condição."""


@dataclass(frozen=True)
class PanoramaHistorico:
    resumo: ResumoGeral
    condicoes: list[ContagemCondicao]
    eventos_por_dia: pd.Series
    eventos_por_rpm: dict[float, int]
    janelas_por_condicao: dict[str, tuple[pd.Timestamp, pd.Timestamp]] = field(
        default_factory=dict
    )


def resumir(eventos: pd.DataFrame) -> PanoramaHistorico:
    """Calcula o panorama do histórico exibido no painel."""
    defeitos = eventos[eventos["tipo_condicao"] == "defeito"]
    estados = eventos[eventos["tipo_condicao"] == "estado"]
    dias = eventos["created_at"].dt.normalize()

    resumo = ResumoGeral(
        total_eventos=len(eventos),
        total_defeitos=len(defeitos),
        total_estados=len(estados),
        familias_de_defeito=defeitos["condicao"].nunique(),
        primeiro_evento=eventos["created_at"].min(),
        ultimo_evento=eventos["created_at"].max(),
        dias_com_registro=int(dias.nunique()),
    )

    contagens: list[ContagemCondicao] = []
    for condicao, grupo in eventos.groupby("condicao"):
        dias_condicao = grupo["created_at"].dt.normalize().nunique()
        contagens.append(
            ContagemCondicao(
                condicao=condicao,
                tipo_condicao=grupo["tipo_condicao"].iloc[0],
                eventos=len(grupo),
                proporcao=len(grupo) / len(eventos),
                primeira=grupo["created_at"].min(),
                ultima=grupo["created_at"].max(),
                dias_com_registro=int(dias_condicao),
                frequencia_diaria=len(grupo) / dias_condicao if dias_condicao else 0.0,
                rotulos_brutos=grupo["fault"].nunique(),
            )
        )
    contagens.sort(key=lambda c: -c.eventos)

    por_dia = eventos.groupby(dias).size()
    por_dia.name = "eventos"
    por_dia.index.name = "dia"

    return PanoramaHistorico(
        resumo=resumo,
        condicoes=contagens,
        eventos_por_dia=por_dia,
        eventos_por_rpm={
            float(rpm): int(total)
            for rpm, total in eventos.groupby("rpm").size().sort_index().items()
        },
        janelas_por_condicao={
            c.condicao: (c.primeira, c.ultima) for c in contagens if c.condicao in DEFEITOS
        },
    )


def validar_taxonomia(panorama: PanoramaHistorico) -> None:
    """Confere que o panorama só contém condições da taxonomia conhecida."""
    conhecidas = DEFEITOS | ESTADOS
    desconhecidas = {c.condicao for c in panorama.condicoes} - conhecidas
    if desconhecidas:
        raise ValueError(f"Condições fora da taxonomia: {sorted(desconhecidas)}")
