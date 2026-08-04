"""Interface da solução de manutenção prescritiva (ADR-002).

Cliente da API, não uma segunda implementação da lógica. Todas as telas conversam com os
mesmos endpoints que um supervisório ou um CMMS usaria.

Execução::

    uvicorn src.api.app:app          # em um terminal
    streamlit run app/main.py        # em outro
"""

from __future__ import annotations

import streamlit as st

from app.cliente import ClienteApi
from app.paginas import analise, chat, documentos, painel

st.set_page_config(
    page_title="Manutenção Prescritiva — SENAI SC",
    page_icon="🔧",
    layout="wide",
)

PAGINAS = {
    "Painel": painel.renderizar,
    "Análise de evento": analise.renderizar,
    "Assistente técnico": chat.renderizar,
    "Base documental": documentos.renderizar,
}


def main() -> None:
    cliente = ClienteApi()

    with st.sidebar:
        st.markdown("### Manutenção Prescritiva")
        st.caption("SENAI SC · sensores de vibração em máquinas rotativas")

        escolha = st.radio("Navegação", list(PAGINAS), label_visibility="collapsed")

        st.divider()
        if cliente.disponivel():
            st.success("API conectada")
        else:
            st.error("API indisponível")
            st.caption("Suba o serviço com `uvicorn src.api.app:app`")

        st.caption(f"Endpoint: `{cliente.base}`")

        st.divider()
        st.caption(
            "As recomendações vêm exclusivamente dos procedimentos técnicos da empresa. "
            "Defeitos sem procedimento cadastrado não recebem recomendação."
        )

    PAGINAS[escolha](cliente)


if __name__ == "__main__":
    main()
