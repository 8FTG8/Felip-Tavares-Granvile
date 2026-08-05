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
    campanhas: list["BlocoDeCampanha"] = field(default_factory=list)


@dataclass(frozen=True)
class BlocoDeCampanha:
    """Trecho contíguo de dias em que um mesmo defeito domina os registros.

    Substituiu um `janelas_por_condicao` que guardava, por condição, o primeiro e o
    último evento. Aquela estatística descrevia mal o histórico: `desbalanceado` é
    ensaiado no fim de abril e volta em junho, então sua janela cobria os 47 dias
    inteiros e se sobrepunha a todas as outras. Medida assim, a afirmação de que as
    campanhas ocupam "janelas quase disjuntas" era simplesmente falsa.

    O bloco contíguo mede o que de fato importa ao ADR-003: **a data carrega informação
    sobre o rótulo**. Em 29 dias com defeito há 18 blocos, e a dominância revela dois
    regimes — até 28/05 os ensaios são limpos (61% a 100% dos eventos do dia num único
    modo de falha), de 01/06 em diante eles se sobrepõem (22% a 63%).

    É essa concentração que faz um classificador validado por amostragem aleatória
    parecer acertar 87% e cair para 11% sob validação por sessão: ele aprendeu o
    calendário, não a vibração.
    """

    condicao: str
    primeiro_dia: pd.Timestamp
    ultimo_dia: pd.Timestamp
    dias: int
    dominancia: float
    """Fração média dos eventos do dia que pertencem à condição dominante."""


def _blocos_de_campanha(defeitos: pd.DataFrame) -> list[BlocoDeCampanha]:
    """Agrupa dias consecutivos que compartilham a mesma condição dominante."""
    if defeitos.empty:
        return []

    dias = defeitos["created_at"].dt.normalize()
    por_dia = defeitos.groupby([dias, defeitos["condicao"]]).size().unstack(fill_value=0)
    participacao = por_dia.div(por_dia.sum(axis=1), axis=0)
    dominante = participacao.idxmax(axis=1)
    fracao = participacao.max(axis=1)

    blocos: list[BlocoDeCampanha] = []
    for dia, condicao in dominante.items():
        anterior = blocos[-1] if blocos else None
        if anterior is not None and anterior.condicao == condicao:
            blocos[-1] = BlocoDeCampanha(
                condicao=condicao,
                primeiro_dia=anterior.primeiro_dia,
                ultimo_dia=dia,
                dias=anterior.dias + 1,
                # Média corrente, para não guardar a lista de frações só para isto.
                dominancia=(anterior.dominancia * anterior.dias + fracao[dia])
                / (anterior.dias + 1),
            )
        else:
            blocos.append(
                BlocoDeCampanha(
                    condicao=condicao,
                    primeiro_dia=dia,
                    ultimo_dia=dia,
                    dias=1,
                    dominancia=float(fracao[dia]),
                )
            )
    return blocos


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
        campanhas=_blocos_de_campanha(defeitos),
    )


def validar_taxonomia(panorama: PanoramaHistorico) -> None:
    """Confere que o panorama só contém condições da taxonomia conhecida."""
    conhecidas = DEFEITOS | ESTADOS
    desconhecidas = {c.condicao for c in panorama.condicoes} - conhecidas
    if desconhecidas:
        raise ValueError(f"Condições fora da taxonomia: {sorted(desconhecidas)}")
