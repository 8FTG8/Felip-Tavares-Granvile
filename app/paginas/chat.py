"""Conversa com o assistente técnico."""

from __future__ import annotations

import streamlit as st

from app.cliente import ApiIndisponivel, ClienteApi
from app.componentes import aviso_api_indisponivel, selo_caminho

CONDICOES = [
    "cocked_rotor",
    "correia",
    "desalinhado",
    "desbalanceado",
    "eccentric_rotor",
    "falta_fase",
    "polia",
    "rolamento_ball",
    "rolamento_combination",
    "rolamento_inner",
    "rolamento_outer",
    "ventoinha",
]

SUGESTOES = {
    "cocked_rotor": ["o eixo pode estar empenado?", "como diferencio de desbalanceamento?"],
    "rolamento_inner": ["falta lubrificação?", "como substituo o rolamento?"],
    "desalinhado": ["como alinho?", "o que é pé manco?"],
    "falta_fase": ["como corrijo?"],
}


def _historico_para_api() -> list[dict]:
    return [
        {"papel": turno["papel"], "conteudo": turno["conteudo"]}
        for turno in st.session_state.conversa
    ]


def renderizar(cliente: ClienteApi) -> None:
    st.title("Assistente técnico")
    st.caption(
        "As respostas vêm exclusivamente dos procedimentos da empresa. Quando não há "
        "procedimento que fundamente a orientação, o assistente diz isso em vez de "
        "improvisar."
    )

    if "conversa" not in st.session_state:
        st.session_state.conversa = []

    esquerda, direita = st.columns([3, 1])
    with esquerda:
        condicao = st.selectbox(
            "Condição do equipamento",
            CONDICOES,
            index=0,
            help=(
                "A condição define qual procedimento responde. Sem ela, o assistente "
                "teria de escolher um documento por conta própria."
            ),
        )
    with direita:
        st.write("")
        st.write("")
        if st.button("Limpar conversa", use_container_width=True):
            st.session_state.conversa = []
            st.rerun()

    if sugestoes := SUGESTOES.get(condicao):
        st.caption("Sugestões: " + " · ".join(f"*{s}*" for s in sugestoes))

    for turno in st.session_state.conversa:
        with st.chat_message("user" if turno["papel"] == "usuario" else "assistant"):
            st.markdown(turno["conteudo"])
            if turno.get("fontes"):
                st.caption("Fontes: " + " · ".join(turno["fontes"]))

    pergunta = st.chat_input("Pergunte sobre a falha…")
    if not pergunta:
        return

    historico = _historico_para_api()
    st.session_state.conversa.append({"papel": "usuario", "conteudo": pergunta})

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
        fontes = roteamento.get("fontes", [])

        if roteamento.get("caminho") and roteamento["caminho"] != "prescricao":
            selo_caminho(roteamento["caminho"], roteamento.get("documento") or None)

        if fontes:
            st.caption("Fontes: " + " · ".join(fontes))

    st.session_state.conversa.append(
        {"papel": "assistente", "conteudo": resposta, "fontes": fontes}
    )
