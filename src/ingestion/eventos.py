"""Carga dos eventos de sensor a partir do ``banner.csv``.

O arquivo traz 166.796 leituras de sensores de vibração instalados em pontos distintos
de uma máquina rotativa. Além da carga em si, este módulo define o subconjunto de
atributos usado pela busca por similaridade (ADR-007) e enriquece cada evento com a
condição canônica correspondente (ADR-005).

Duas observações sobre a fonte, registradas na análise exploratória:

* ``banner.xlsx`` **não deve ser usado**: os valores decimais foram gravados de forma
  corrompida e intermitente (``0.0427`` aparece como ``427.0``, misturando texto e
  número na mesma coluna). O CSV é a única fonte confiável.
* ``created_at`` nunca entra como atributo do modelo. Cada família de defeito foi
  coletada em uma janela temporal quase disjunta, de modo que a data prediz o rótulo
  quase perfeitamente — é vazamento puro. Seu lugar é na saída, alimentando a
  distribuição temporal das ocorrências semelhantes pedida pelo enunciado.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ingestion.rotulos import normalizar

#: Atributos usados pela busca por similaridade (ADR-007). São 18 dos 25 numéricos: as
#: demais colunas são transformações exatas destas — conversão de unidade (in/s ↔ mm/s,
#: °F ↔ °C) ou derivação interna do firmware (``peak_velocity = rms_velocity × √2``).
#: Mantê-las daria peso triplo ao eixo de velocidade na distância euclidiana.
ATRIBUTOS: tuple[str, ...] = (
    "z_rms_velocity_mm_s",
    "x_rms_velocity_mm_s",
    "z_peak_acceleration_g",
    "x_peak_acceleration_g",
    "z_rms_acceleration_g",
    "x_rms_acceleration_g",
    "z_high_freq_rms_accel_g",
    "x_high_freq_rms_accel_g",
    "z_peak_vel_comp_freq_hz",
    "x_peak_vel_comp_freq_hz",
    "z_kurtosis",
    "x_kurtosis",
    "z_crest_factor",
    "x_crest_factor",
    "temperature_c",
    "rpm",
)

#: Colunas redundantes, descartadas na carga. Ver ADR-007.
REDUNDANTES: tuple[str, ...] = (
    "z_rms_velocity_in_s",
    "x_rms_velocity_in_s",
    "z_peak_velocity_in_s",
    "x_peak_velocity_in_s",
    "z_peak_velocity_mm_s",
    "x_peak_velocity_mm_s",
    "temperature_f",
)

#: Valor de saturação do registrador uint16 do sensor (2¹⁶ − 1). Leituras de curtose
#: neste valor são censuradas, não medições físicas.
SATURACAO_KURTOSIS = 65.535


def caminho_padrao() -> Path:
    """Caminho do ``banner.csv`` completo, relativo à raiz do projeto."""
    return Path(__file__).resolve().parents[2] / "docs" / "dados" / "banner.csv"


def carregar_eventos(caminho: Path | str | None = None) -> pd.DataFrame:
    """Carrega os eventos, descarta colunas redundantes e anexa a condição canônica.

    Colunas acrescentadas:

    ``condicao``
        forma canônica do rótulo — uma das 17 condições ou ``desconhecido``.
    ``tipo_condicao``
        ``defeito``, ``estado`` ou ``desconhecido``.
    ``kurtosis_saturada``
        indica leitura em que a curtose atingiu o limite do registrador.
    """
    origem = Path(caminho) if caminho is not None else caminho_padrao()
    if not origem.exists():
        raise FileNotFoundError(
            f"Arquivo de eventos não encontrado: {origem}. "
            "Consulte o README para o download do conjunto completo."
        )

    eventos = pd.read_csv(origem, parse_dates=["created_at"])
    eventos = eventos.drop(columns=list(REDUNDANTES), errors="ignore")

    condicoes = eventos["fault"].map(normalizar)
    eventos["condicao"] = [c.canonico for c in condicoes]
    eventos["tipo_condicao"] = [c.tipo.value for c in condicoes]
    eventos["kurtosis_saturada"] = (eventos["z_kurtosis"] >= SATURACAO_KURTOSIS) | (
        eventos["x_kurtosis"] >= SATURACAO_KURTOSIS
    )

    return eventos


def apenas_defeitos(eventos: pd.DataFrame) -> pd.DataFrame:
    """Recorta os eventos cuja condição é um defeito, excluindo estados do sistema."""
    return eventos[eventos["tipo_condicao"] == "defeito"]
