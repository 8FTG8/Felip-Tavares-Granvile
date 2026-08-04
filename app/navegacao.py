"""Barra lateral e navegação.

Segue o padrão de navegação em superfície clara: marca no topo, itens com ícone em traço,
item corrente marcado por uma pílula cinza suave em vez de cor saturada, e contadores em
chip discreto. A hierarquia é comunicada por peso e espaçamento, não por contraste forte —
a barra lateral orienta, não disputa atenção com o conteúdo.

Os defeitos sem procedimento aparecem como sub-itens do destino *Documentos*, ligados por
uma guia vertical. Não é enfeite: responde, sem que ninguém precise abrir a tela, à única
pergunta que o operador faz o tempo todo — *o que ainda está sem procedimento?*
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from app import estilo
from app.cliente import ApiIndisponivel, ClienteApi


@dataclass(frozen=True)
class Destino:
    chave: str
    rotulo: str
    icone: str
    descricao: str


#: Agrupados por natureza da tarefa: o que se faz no dia a dia e o que se configura.
#: Quatro itens soltos não formam uma lista legível; agrupados, formam.
SECOES: tuple[tuple[str, tuple[Destino, ...]], ...] = (
    (
        "Operação",
        (
            Destino("Painel", "Painel", "monitoring", "Panorama do histórico"),
            Destino("Análise de evento", "Análise de evento", "vital_signs", "Leitura de sensor"),
            Destino("Assistente técnico", "Assistente técnico", "forum", "Conversa técnica"),
        ),
    ),
    (
        "Configuração",
        (Destino("Base documental", "Documentos", "description", "Procedimentos técnicos"),),
    ),
)

DESTINOS = tuple(destino for _, grupo in SECOES for destino in grupo)

_PADRAO = DESTINOS[0].chave

_CSS = f"""
<style>
[data-testid="stSidebar"] {{
    background: {estilo.SUPERFICIE};
    border-right: 1px solid {estilo.BORDA};
    min-width: 272px;
}}
[data-testid="stSidebar"] * {{ color: {estilo.TINTA}; }}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 2px; }}
[data-testid="stSidebar"] hr {{
    border-color: {estilo.BORDA};
    margin: {estilo.ESPACO["md"]}px 0;
}}

/* Item de navegação: sem moldura, estado ativo por preenchimento suave.
   A pílula cinza marca a posição sem competir com o conteúdo da página. */
[data-testid="stSidebar"] .stButton > button {{
    width: 100%;
    justify-content: flex-start;
    text-align: left;
    background: transparent;
    border: none;
    border-radius: {estilo.RAIO["lg"]}px;
    color: {estilo.TINTA_SECUNDARIA};
    font-weight: 500;
    padding: {estilo.ESPACO["sm"]}px {estilo.ESPACO["md"]}px;
    box-shadow: none;
    transform: none;
    transition: background 150ms ease, color 150ms ease;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: {estilo.SUPERFICIE_ALTERNATIVA};
    color: {estilo.TINTA};
    transform: none;
    box-shadow: none;
}}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
    background: {estilo.SUPERFICIE_ATIVA};
    color: {estilo.TINTA};
    font-weight: 600;
    box-shadow: inset 0 0 0 1px rgba(15,23,42,0.06);
}}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {{
    background: #E8EEF4;
}}
[data-testid="stSidebar"] .stButton > button p {{ font-size: 0.9rem; }}
[data-testid="stSidebar"] .stButton > button [data-testid="stIconMaterial"] {{
    font-size: 19px;
    margin-right: 2px;
}}
</style>
"""


def _cabecalho() -> None:
    """Marca do produto: tile do logo e nome, seguidos de um separador."""
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:{estilo.ESPACO['md']}px;
                    padding:{estilo.ESPACO['sm']}px {estilo.ESPACO['xs']}px
                            {estilo.ESPACO['lg']}px">
          <div style="width:34px;height:34px;border-radius:{estilo.RAIO['md']}px;
                      background:{estilo.MARCA};display:flex;align-items:center;
                      justify-content:center;flex-shrink:0">
            <span style="font-size:17px;line-height:1;filter:grayscale(1) brightness(3)">⚙</span>
          </div>
          <div style="line-height:1.2">
            <div style="font-size:0.98rem;font-weight:700;color:{estilo.TINTA};
                        letter-spacing:-0.015em">Manutenção</div>
            <div style="font-size:0.98rem;font-weight:700;color:{estilo.TINTA};
                        letter-spacing:-0.015em;margin-top:-3px">Prescritiva</div>
          </div>
        </div>
        <div style="height:1px;background:{estilo.BORDA};
                    margin:0 0 {estilo.ESPACO['md']}px"></div>
        """,
        unsafe_allow_html=True,
    )


def _rotulo_secao(texto: str, espaco_acima: int = 0) -> None:
    st.markdown(
        f"<div style='font-size:0.75rem;color:{estilo.TINTA_SUAVE};font-weight:500;"
        f"margin:{espaco_acima}px 0 {estilo.ESPACO['xs']}px {estilo.ESPACO['md']}px'>"
        f"{texto}</div>",
        unsafe_allow_html=True,
    )


def _pendencias(cliente: ClienteApi) -> list[str] | None:
    """Defeitos que aguardam cadastro de procedimento.

    Devolve ``None`` quando a API não responde — a navegação continua utilizável sem os
    contadores, que são informação acessória.
    """
    try:
        return [s["condicao"] for s in cliente.cobertura() if not s["documentada"]]
    except ApiIndisponivel:
        return None
    except Exception:
        return None


def _subitens(condicoes: list[str]) -> None:
    """Lista os defeitos pendentes sob o destino *Documentos*, ligados por uma guia."""
    itens = "".join(
        f"""
        <div style="position:relative;padding:5px 0 5px {estilo.ESPACO['lg']}px;
                    font-size:0.82rem;color:{estilo.TINTA_SECUNDARIA}">
          <span style="position:absolute;left:0;top:50%;width:9px;height:1px;
                       background:{estilo.BORDA}"></span>
          <span style="display:inline-block;width:6px;height:6px;border-radius:50%;
                       background:{estilo.ALERTA};margin-right:7px;
                       vertical-align:middle"></span>{condicao}
        </div>
        """
        for condicao in condicoes
    )
    st.markdown(
        f"""
        <div style="position:relative;margin:2px 0 {estilo.ESPACO['sm']}px
                    {estilo.ESPACO['xl']}px">
          <span style="position:absolute;left:0;top:0;bottom:12px;width:1px;
                       background:{estilo.BORDA}"></span>
          {itens}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _chip(texto: str) -> str:
    return f"  ({texto})"


def _navegacao(pendentes: list[str] | None) -> str:
    if "pagina" not in st.session_state:
        st.session_state.pagina = _PADRAO

    for indice, (secao, destinos) in enumerate(SECOES):
        _rotulo_secao(secao, espaco_acima=0 if indice == 0 else estilo.ESPACO["lg"])

        for destino in destinos:
            ativo = st.session_state.pagina == destino.chave
            rotulo = destino.rotulo
            if destino.chave == "Base documental" and pendentes:
                rotulo += _chip(str(len(pendentes)))

            if st.button(
                rotulo,
                key=f"nav_{destino.chave}",
                icon=f":material/{destino.icone}:",
                type="primary" if ativo else "secondary",
                use_container_width=True,
                help=destino.descricao,
            ):
                st.session_state.pagina = destino.chave
                st.rerun()

            if destino.chave == "Base documental" and pendentes:
                _subitens(pendentes)

    return st.session_state.pagina


def _linha_estado(rotulo: str, valor: str) -> str:
    return (
        f"<div style='display:flex;justify-content:space-between;align-items:center;"
        f"padding:4px 0'>"
        f"<span style='font-size:0.75rem;color:{estilo.TINTA_SUAVE}'>{rotulo}</span>"
        f"<span style='font-size:0.75rem;color:{estilo.TINTA_SECUNDARIA};"
        f"font-weight:500'>{valor}</span></div>"
    )


def _cartao_sistema(cliente: ClienteApi) -> None:
    """Estado do serviço em um bloco só: conexão, modelo, limiar e cobertura.

    Reúne o que a demonstração precisa ter à vista — sobretudo o modelo em uso, que é a
    primeira pergunta de quem avalia uma solução com LLM local.
    """
    _rotulo_secao("Sistema", espaco_acima=estilo.ESPACO["lg"])

    try:
        sistema = cliente.sistema()
    except Exception:
        sistema = None

    conectada = sistema is not None
    cor = estilo.SUCESSO if conectada else estilo.CRITICO
    texto = "API conectada" if conectada else "API indisponível"

    linhas = ""
    if sistema:
        linhas = (
            f"<div style='height:1px;background:{estilo.BORDA};margin:8px 0'></div>"
            + _linha_estado("Modelo", sistema["modelo"].split(":")[0])
            + _linha_estado("Variante", sistema["modelo"].split(":")[-1])
            + _linha_estado("Limiar", f"{sistema['limiar_relevancia']:.3f}")
            + _linha_estado(
                "Cobertura",
                f"{sistema['familias_documentadas']}/{sistema['familias_totais']} famílias",
            )
        )

    st.markdown(
        f"""
        <div style="border:1px solid {estilo.BORDA};border-radius:{estilo.RAIO['md']}px;
                    padding:{estilo.ESPACO['md']}px;
                    background:{estilo.SUPERFICIE_ALTERNATIVA}">
          <div style="display:flex;align-items:center;gap:{estilo.ESPACO['sm']}px">
            <span style="width:7px;height:7px;border-radius:50%;background:{cor};
                         flex-shrink:0;box-shadow:0 0 0 3px {cor}22"></span>
            <span style="font-size:0.8rem;font-weight:500;color:{estilo.TINTA}">{texto}</span>
          </div>
          {linhas}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not conectada:
        st.caption("Suba o serviço: `uvicorn src.api.app:app`")


def _rodape() -> None:
    st.markdown(
        f"""
        <div style="margin-top:{estilo.ESPACO['lg']}px;
                    padding-top:{estilo.ESPACO['md']}px;
                    border-top:1px solid {estilo.BORDA};
                    font-size:0.72rem;color:{estilo.TINTA_SUAVE};line-height:1.55">
          As recomendações vêm exclusivamente dos procedimentos técnicos da empresa.
          Defeitos sem procedimento cadastrado não recebem recomendação.
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderizar(cliente: ClienteApi) -> str:
    """Desenha a barra lateral e devolve a página escolhida."""
    with st.sidebar:
        st.markdown(_CSS, unsafe_allow_html=True)
        _cabecalho()
        escolha = _navegacao(_pendencias(cliente))
        _cartao_sistema(cliente)
        _rodape()
    return escolha
