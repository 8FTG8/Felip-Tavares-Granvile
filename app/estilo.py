"""Design system da interface.

Os tokens reproduzem o sistema já usado pelo autor na plataforma Caree — mesma escala de
espaçamento, mesmos raios, mesmas sombras em duas camadas e a mesma paleta semântica.
Reaproveitar um sistema existente em vez de inventar outro dá coerência visual sem custo de
decisão, e mantém a interface reconhecível para quem conhece os demais produtos.

A paleta de gráficos foi verificada quanto a legibilidade sob daltonismo: o par
verde/laranja usado na cobertura documental mantém separação perceptual suficiente em
deuteranopia e tritanopia. Como as cores ficam abaixo de 3:1 de contraste com o fundo, os
gráficos trazem rótulos diretos e a tabela completa logo abaixo — a cor nunca é o único
portador da informação.
"""

from __future__ import annotations

import streamlit as st

# ── Cores ────────────────────────────────────────────────────────────────────────

MARCA = "#0D1929"
"""Azul-marinho escuro: títulos e barra lateral."""

ACENTO = "#1D4ED8"
"""Azul vívido: ações primárias e séries neutras de gráfico."""

SUCESSO = "#10B981"
ALERTA = "#F57C00"
CRITICO = "#D62828"

TINTA = "#0D1929"
TINTA_SECUNDARIA = "#475569"
TINTA_SUAVE = "#94A3B8"

SUPERFICIE = "#FFFFFF"
SUPERFICIE_ALTERNATIVA = "#F6F7F9"
BORDA = "#E2E8F0"

GRADE = "#EEF1F5"
"""Linhas de grade: presentes o bastante para orientar, discretas o bastante para recuar."""

# ── Espaçamento e raios ──────────────────────────────────────────────────────────

ESPACO = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32, "xxxl": 48}
RAIO = {"sm": 4, "md": 8, "lg": 12, "xl": 16, "cheio": 999}

FONTE = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

# ── Gráficos ─────────────────────────────────────────────────────────────────────

#: Altura padrão dos gráficos, em pixels.
ALTURA_GRAFICO = 320

LAYOUT_GRAFICO = {
    "font": {"family": FONTE, "size": 12, "color": TINTA_SECUNDARIA},
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "margin": {"l": 8, "r": 8, "t": 8, "b": 8},
    "hoverlabel": {
        "bgcolor": SUPERFICIE,
        "bordercolor": BORDA,
        "font": {"family": FONTE, "size": 12, "color": TINTA},
    },
    "xaxis": {"gridcolor": GRADE, "linecolor": BORDA, "zeroline": False},
    "yaxis": {"gridcolor": GRADE, "linecolor": BORDA, "zeroline": False},
    "legend": {"orientation": "h", "y": 1.1, "x": 0, "title": {"text": ""}},
}


def aplicar_layout(figura, altura: int = ALTURA_GRAFICO):
    """Aplica o layout comum a uma figura Plotly."""
    figura.update_layout(**LAYOUT_GRAFICO, height=altura)
    return figura


# ── Folha de estilo ──────────────────────────────────────────────────────────────

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {{
    font-family: {FONTE};
}}

.stApp {{
    background: {SUPERFICIE_ALTERNATIVA};
}}

.block-container {{
    padding-top: {ESPACO["xl"]}px;
    padding-bottom: {ESPACO["xxxl"]}px;
    max-width: 1240px;
}}

h1, h2, h3, h4 {{
    color: {TINTA};
    font-weight: 600;
    letter-spacing: -0.015em;
}}

h1 {{ font-size: 1.75rem !important; margin-bottom: {ESPACO["xs"]}px !important; }}
h2 {{ font-size: 1.25rem !important; }}
h3 {{ font-size: 1.05rem !important; }}

/* Cartões: sombra em duas camadas (ambiente + direcional), sem borda pesada. */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
    background: {SUPERFICIE};
    border: 1px solid {BORDA};
    border-radius: {RAIO["lg"]}px;
    padding: {ESPACO["lg"]}px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.04), 0 3px 12px rgba(0,0,0,0.06);
}}

[data-testid="stMetric"] {{
    background: {SUPERFICIE};
    border: 1px solid {BORDA};
    border-radius: {RAIO["lg"]}px;
    padding: {ESPACO["lg"]}px {ESPACO["lg"]}px {ESPACO["md"]}px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03);
}}

[data-testid="stMetricLabel"] p {{
    font-size: 0.78rem !important;
    font-weight: 500;
    color: {TINTA_SECUNDARIA};
    letter-spacing: 0.01em;
}}

[data-testid="stMetricValue"] {{
    font-size: 1.6rem;
    font-weight: 600;
    color: {TINTA};
    letter-spacing: -0.02em;
}}

/* Barra lateral: marca escura, para separar o chrome do conteúdo. */
[data-testid="stSidebar"] {{
    background: {MARCA};
    border-right: none;
}}
[data-testid="stSidebar"] * {{ color: #E8EDF5; }}
[data-testid="stSidebar"] h3 {{ color: #FFFFFF; font-size: 1rem !important; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
    color: #8FA3BF !important;
    font-size: 0.78rem;
}}
[data-testid="stSidebar"] [role="radiogroup"] label {{
    padding: {ESPACO["sm"]}px {ESPACO["md"]}px;
    border-radius: {RAIO["md"]}px;
    transition: background 150ms ease;
}}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {{
    background: rgba(255,255,255,0.06);
}}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.12); }}

.stButton > button {{
    border-radius: {RAIO["md"]}px;
    font-weight: 500;
    padding: {ESPACO["sm"]}px {ESPACO["lg"]}px;
    transition: transform 150ms ease, box-shadow 150ms ease;
}}
.stButton > button[kind="primary"] {{
    background: {ACENTO};
    border-color: {ACENTO};
    box-shadow: 0 1px 4px rgba(29,78,216,0.24);
}}
.stButton > button[kind="primary"]:hover {{
    box-shadow: 0 3px 10px rgba(29,78,216,0.3);
    transform: translateY(-1px);
}}

[data-testid="stChatMessage"] {{
    background: {SUPERFICIE};
    border: 1px solid {BORDA};
    border-radius: {RAIO["lg"]}px;
    padding: {ESPACO["md"]}px {ESPACO["lg"]}px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03);
    margin-bottom: {ESPACO["sm"]}px;
}}

[data-testid="stAlert"] {{
    border-radius: {RAIO["md"]}px;
    border-width: 1px;
    box-shadow: none;
}}

.stDataFrame, [data-testid="stDataFrame"] {{
    border-radius: {RAIO["md"]}px;
    overflow: hidden;
    border: 1px solid {BORDA};
}}

[data-testid="stExpander"] details {{
    border: 1px solid {BORDA};
    border-radius: {RAIO["md"]}px;
    background: {SUPERFICIE};
}}

[data-testid="stTabs"] button {{ font-weight: 500; }}

#MainMenu, footer, [data-testid="stDecoration"] {{ visibility: hidden; }}
</style>
"""


def aplicar() -> None:
    """Injeta a folha de estilo. Deve ser chamada uma vez, no início da aplicação."""
    st.markdown(_CSS, unsafe_allow_html=True)


def cabecalho(titulo: str, descricao: str) -> None:
    """Cabeçalho padrão de página: título e uma linha explicando o que a tela faz."""
    st.markdown(
        f"<h1>{titulo}</h1>"
        f"<p style='color:{TINTA_SECUNDARIA};font-size:0.95rem;margin-top:-4px;"
        f"margin-bottom:{ESPACO['xl']}px'>{descricao}</p>",
        unsafe_allow_html=True,
    )
