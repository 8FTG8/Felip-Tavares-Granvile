"""Conversa com o assistente técnico."""

from __future__ import annotations

import streamlit as st

from app import estilo
from app.cliente import ApiIndisponivel, ClienteApi
from app.componentes import aviso_api_indisponivel, selo_caminho

CONDICOES = [
    "cocked_rotor",
    "rolamento_inner",
    "rolamento_outer",
    "rolamento_ball",
    "rolamento_combination",
    "desalinhado",
    "desbalanceado",
    "correia",
    "polia",
    "eccentric_rotor",
    "ventoinha",
    "falta_fase",
]

SUGESTOES = {
    "cocked_rotor": ["o eixo pode estar empenado?", "como diferencio de desbalanceamento?"],
    "rolamento_inner": ["falta lubrificação?", "como substituo o rolamento?"],
    "desalinhado": ["como alinho?", "o que é pé manco?"],
    "desbalanceado": ["preciso balancear?", "como calculo a massa de correção?"],
    "correia": ["a correia está frouxa?"],
    "polia": ["a polia está gasta?"],
    "falta_fase": ["como corrijo?"],
    "eccentric_rotor": ["como corrijo?"],
    "ventoinha": ["como corrijo?"],
}


def _historico_para_api() -> list[dict]:
    return [
        {"papel": turno["papel"], "conteudo": turno["conteudo"]}
        for turno in st.session_state.conversa
    ]


def _fontes(fontes: list[str]) -> None:
    if not fontes:
        return
    st.markdown(
        f"<p style='font-size:0.74rem;color:{estilo.TINTA_SUAVE};margin-top:6px'>"
        "Fontes: " + " · ".join(fontes) + "</p>",
        unsafe_allow_html=True,
    )


def _trilho(condicao: str) -> None:
    """Contexto da conversa: condição ativa, documento roteado e fontes da última fala."""
    with estilo.cartao("Contexto"):
        roteamento = st.session_state.get("roteamento_chat") or {}
        documento = roteamento.get("documento") or "—"

        st.markdown(
            f"""
            <div style="font-size:0.72rem;color:{estilo.TINTA_SUAVE};
                        text-transform:uppercase;letter-spacing:0.06em">Condição</div>
            <div style="font-size:0.92rem;font-weight:600;color:{estilo.TINTA};
                        margin-bottom:{estilo.ESPACO['md']}px">{condicao}</div>
            <div style="font-size:0.72rem;color:{estilo.TINTA_SUAVE};
                        text-transform:uppercase;letter-spacing:0.06em">Procedimento</div>
            <div style="font-size:0.92rem;font-weight:600;color:{estilo.TINTA}">
              {documento}</div>
            """,
            unsafe_allow_html=True,
        )

        if roteamento.get("caminho"):
            st.write("")
            selo_caminho(roteamento["caminho"])

        fontes = roteamento.get("fontes") or []
        if fontes:
            st.markdown(
                f"<div style='font-size:0.72rem;color:{estilo.TINTA_SUAVE};"
                "text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px'>"
                "Seções citadas</div>",
                unsafe_allow_html=True,
            )
            for fonte in fontes:
                st.markdown(
                    f"<div style='font-size:0.79rem;color:{estilo.TINTA_SECUNDARIA};"
                    f"padding:5px 0;border-bottom:1px solid {estilo.BORDA}'>{fonte}</div>",
                    unsafe_allow_html=True,
                )

    with estilo.cartao("Sugestões"):
        for sugestao in SUGESTOES.get(condicao, ["como corrijo?"]):
            st.markdown(
                f"<div style='font-size:0.81rem;color:{estilo.TINTA_SECUNDARIA};"
                f"background:{estilo.SUPERFICIE_ALTERNATIVA};border-radius:"
                f"{estilo.RAIO['md']}px;padding:7px 11px;margin-bottom:6px'>"
                f"{sugestao}</div>",
                unsafe_allow_html=True,
            )


def renderizar(cliente: ClienteApi) -> None:
    if "conversa" not in st.session_state:
        st.session_state.conversa = []

    etiquetas: tuple[str, ...] = ()
    try:
        sistema = cliente.sistema()
        etiquetas = (estilo.chip(sistema["modelo"], estilo.SUCESSO, icone="ponto"),)
    except ApiIndisponivel:
        pass

    if estilo.topo(
        "Assistente técnico",
        "As respostas vêm exclusivamente dos procedimentos da empresa. Sem procedimento "
        "que a fundamente, o assistente diz isso em vez de improvisar.",
        etiquetas=etiquetas,
        acao="Limpar conversa",
        icone_acao="restart_alt",
    ):
        st.session_state.conversa = []
        st.session_state.roteamento_chat = {}
        st.rerun()

    conversa, trilho = st.columns([3, 1])

    with conversa:
        condicao = st.selectbox(
            "Condição do equipamento",
            CONDICOES,
            help=(
                "A condição define qual procedimento responde. Sem ela, o assistente "
                "teria de escolher um documento por conta própria."
            ),
        )

        for turno in st.session_state.conversa:
            with st.chat_message("user" if turno["papel"] == "usuario" else "assistant"):
                st.markdown(turno["conteudo"])
                _fontes(turno.get("fontes", []))

    with trilho:
        _trilho(condicao)

    pergunta = st.chat_input("Pergunte sobre a falha…")
    if not pergunta:
        return

    historico = _historico_para_api()
    st.session_state.conversa.append({"papel": "usuario", "conteudo": pergunta})

    with conversa:
        with st.chat_message("user"):
            st.markdown(pergunta)

        with st.chat_message("assistant"):
            try:
                resposta = st.write_stream(
                    cliente.conversar_em_fluxo(pergunta, condicao, historico)
                )
            except ApiIndisponivel:
                aviso_api_indisponivel()
                st.session_state.conversa.pop()
                return

            # O roteamento e as citações vieram nos cabeçalhos, junto com o início do
            # fluxo — sem custo de uma segunda geração.
            roteamento = cliente.ultimo_roteamento
            st.session_state.roteamento_chat = roteamento
            fontes = roteamento.get("fontes", [])
            _fontes(fontes)

    st.session_state.conversa.append(
        {"papel": "assistente", "conteudo": resposta, "fontes": fontes}
    )
