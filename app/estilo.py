"""Design system da interface.

A paleta tem **quatro cores cromáticas e uma rampa neutra** — nada além disso. Cada cor
carrega um significado fixo, e a escassez é intencional: quando tudo é colorido, cor deixa
de informar. A estrutura da escala de espaçamento, dos raios e das sombras em duas camadas
segue o sistema que o autor já usa em outros produtos; a identidade cromática é própria
deste projeto.

**Regra de uso.** O acento pode aparecer em qualquer lugar — ação primária, item de
navegação corrente, série única de gráfico. As três cores de status são reservadas e nunca
viram "mais uma série": verde significa sempre *coberto por procedimento*, âmbar sempre
*sem respaldo documental*, vermelho sempre *falha*. É o que permite ler o painel de
relance.

**Verificação de acessibilidade.** As quatro cores foram medidas com o validador de
paletas em visão normal, protanopia, deuteranopia e tritanopia. Todas mantêm contraste
mínimo de 3:1 com a superfície e separação de ΔE 18,5 no pior par sob visão normal. O par
âmbar/verde fica em ΔE 7,9 sob protanopia — faixa que só é admissível com codificação
secundária, e por isso os gráficos que os usam juntos trazem rótulos diretos, legenda e a
tabela completa logo abaixo. A cor nunca é o único portador da informação.
"""

from __future__ import annotations

from contextlib import contextmanager

import streamlit as st

# ── Cores ────────────────────────────────────────────────────────────────────────

ACENTO = "#0369A1"
"""Azul-petróleo: ações primárias, item de navegação corrente e série única de gráfico."""

SUCESSO = "#059669"
"""Defeito coberto por procedimento; serviço no ar."""

ALERTA = "#D97706"
"""Defeito sem respaldo documental; recusa do guardrail."""

CRITICO = "#BE123C"
"""Falha de operação: entrada inválida, serviço indisponível."""

TINTA = "#0F172A"
TINTA_SECUNDARIA = "#475569"
TINTA_SUAVE = "#94A3B8"

MARCA = TINTA
"""A marca não tem cor própria: é a tinta mais escura, para não competir com o status."""

SUPERFICIE = "#FFFFFF"
SUPERFICIE_ALTERNATIVA = "#F8FAFC"
SUPERFICIE_ATIVA = "#F1F5F9"
"""Preenchimento do item selecionado — hierarquia por tom, não por saturação."""

BORDA = "#E2E8F0"

GRADE = "#EEF2F6"
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
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

/* Ícones em traço, no mesmo peso do texto — acompanham o rótulo sem dominá-lo. */
.material-symbols-outlined {{
    font-family: 'Material Symbols Outlined';
    font-weight: normal;
    font-style: normal;
    line-height: 1;
    vertical-align: -3px;
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 20;
}}

html, body, [class*="css"], .stApp {{
    font-family: {FONTE};
}}

.stApp {{
    background: {SUPERFICIE_ALTERNATIVA};
}}

/* Cartões: superfície branca sobre o fundo do aplicativo, com sombra em duas camadas
   (ambiente + direcional) em vez de borda pesada. */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {SUPERFICIE};
    border: 1px solid {BORDA};
    border-radius: {RAIO["lg"]}px;
    padding: {ESPACO["lg"]}px {ESPACO["xl"]}px {ESPACO["xl"]}px;
    box-shadow: 0 1px 4px rgba(15,23,42,0.03), 0 4px 14px rgba(15,23,42,0.04);
}}
/* Molduras aninhadas viram ruído: o cartão interno recua para superfície plana. */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"] {{
    box-shadow: none;
    background: {SUPERFICIE_ALTERNATIVA};
    padding: {ESPACO["md"]}px {ESPACO["lg"]}px;
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

/* A barra lateral tem folha própria em app/navegacao.py, que define sua superfície
   clara e o estado ativo dos destinos. */
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
    font-size: 0.76rem;
    color: {TINTA_SUAVE};
}}

.stButton > button {{
    border-radius: {RAIO["md"]}px;
    font-weight: 500;
    padding: {ESPACO["sm"]}px {ESPACO["lg"]}px;
    transition: transform 150ms ease, box-shadow 150ms ease;
}}
.stButton > button[kind="primary"] {{
    background: {ACENTO};
    border-color: {ACENTO};
    box-shadow: 0 1px 4px rgba(3,105,161,0.22);
}}
.stButton > button[kind="primary"]:hover {{
    box-shadow: 0 3px 10px rgba(3,105,161,0.28);
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


def chip(texto: str, cor: str = TINTA_SECUNDARIA, icone: str = "") -> str:
    """Etiqueta compacta para metadados — modelo em uso, contagens, estado."""
    marca = (
        f"<span style='width:6px;height:6px;border-radius:50%;background:{cor};"
        f"display:inline-block;margin-right:6px'></span>"
        if icone == "ponto"
        else ""
    )
    return (
        f"<span style='display:inline-flex;align-items:center;font-size:0.75rem;"
        f"color:{TINTA_SECUNDARIA};background:{SUPERFICIE_ALTERNATIVA};"
        f"border:1px solid {BORDA};border-radius:{RAIO['cheio']}px;"
        f"padding:3px 10px;white-space:nowrap'>{marca}{texto}</span>"
    )


def topo(
    titulo: str,
    descricao: str,
    etiquetas: tuple[str, ...] = (),
    acao: str | None = None,
    icone_acao: str | None = None,
) -> bool:
    """Cabeçalho de página: título, descrição, etiquetas de contexto e ação primária.

    A ação fica à direita do título, como nas telas de referência — o usuário encontra o
    que fazer na página sem procurar. Devolve ``True`` quando o botão é acionado.

    O Streamlit não fixa a faixa ao rolar; ela acompanha o conteúdo. Preferiu-se isso a
    simular fixação com CSS, que quebra a rolagem interna dos gráficos.
    """
    esquerda, direita = st.columns([7, 3], vertical_alignment="center")

    with esquerda:
        st.markdown(
            f"<h1 style='margin-bottom:2px'>{titulo}</h1>"
            f"<p style='color:{TINTA_SECUNDARIA};font-size:0.9rem;margin:0'>{descricao}</p>",
            unsafe_allow_html=True,
        )

    acionado = False
    with direita:
        if etiquetas:
            st.markdown(
                "<div style='display:flex;gap:6px;justify-content:flex-end;flex-wrap:wrap;"
                f"margin-bottom:{ESPACO['sm']}px'>" + "".join(etiquetas) + "</div>",
                unsafe_allow_html=True,
            )
        if acao:
            acionado = st.button(
                acao,
                type="primary",
                use_container_width=True,
                icon=f":material/{icone_acao}:" if icone_acao else None,
            )

    st.markdown(
        f"<div style='height:1px;background:{BORDA};margin:{ESPACO['lg']}px 0 "
        f"{ESPACO['xl']}px'></div>",
        unsafe_allow_html=True,
    )
    return acionado


@contextmanager
def cartao(titulo: str | None = None, complemento: str | None = None):
    """Bloco de conteúdo em superfície branca sobre o fundo do aplicativo.

    O cartão agrupa uma unidade de informação e a separa das demais — é o que dá
    estrutura à página sem depender de divisores sucessivos.
    """
    with st.container(border=True):
        if titulo:
            extra = (
                f"<span style='font-size:0.78rem;color:{TINTA_SUAVE};margin-left:auto'>"
                f"{complemento}</span>"
                if complemento
                else ""
            )
            st.markdown(
                f"<div style='display:flex;align-items:baseline;gap:{ESPACO['sm']}px;"
                f"margin-bottom:{ESPACO['md']}px'>"
                f"<span style='font-size:1rem;font-weight:600;color:{TINTA}'>{titulo}</span>"
                f"{extra}</div>",
                unsafe_allow_html=True,
            )
        yield


def cabecalho(titulo: str, descricao: str) -> None:
    """Compatibilidade: cabeçalho sem etiquetas nem ação."""
    topo(titulo, descricao)
