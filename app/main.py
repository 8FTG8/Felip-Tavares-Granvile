"""Interface da solução de manutenção prescritiva (ADR-002).

Cliente da API, não uma segunda implementação da lógica. Todas as telas conversam com os
mesmos endpoints que um supervisório ou um CMMS usaria.

Execução::

    uvicorn src.api.app:app          # em um terminal
    streamlit run app/main.py        # em outro
"""

from __future__ import annotations

import streamlit as st

from app import estilo, navegacao
from app.cliente import ClienteApi
from app.paginas import analise, chat, documentos, painel

st.set_page_config(
    page_title="Manutenção Prescritiva — SENAI SC",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGINAS = {
    "Painel": painel.renderizar,
    "Análise de evento": analise.renderizar,
    "Assistente técnico": chat.renderizar,
    "Base documental": documentos.renderizar,
}


def main() -> None:
    estilo.aplicar()
    cliente = ClienteApi()
    PAGINAS[navegacao.renderizar(cliente)](cliente)


if __name__ == "__main__":
    main()
