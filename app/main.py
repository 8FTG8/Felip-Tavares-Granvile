"""Interface da solução de manutenção prescritiva (ADR-002).

Cliente da API, não uma segunda implementação da lógica. Todas as telas conversam com os
mesmos endpoints que um supervisório ou um CMMS usaria.

Execução::

    uvicorn src.api.app:app          # em um terminal
    streamlit run app/main.py        # em outro
"""

from __future__ import annotations

import streamlit as st

from app import estilo
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


def _barra_lateral(cliente: ClienteApi) -> str:
    with st.sidebar:
        st.markdown(
            f"""
            <div style="padding:{estilo.ESPACO['sm']}px 0 {estilo.ESPACO['lg']}px">
              <div style="font-size:1.05rem;font-weight:600;color:#FFFFFF">
                Manutenção Prescritiva
              </div>
              <div style="font-size:0.78rem;color:#8FA3BF;margin-top:2px">
                SENAI SC · máquinas rotativas
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        escolha = st.radio("Navegação", list(PAGINAS), label_visibility="collapsed")

        st.divider()

        conectada = cliente.disponivel()
        cor = estilo.SUCESSO if conectada else estilo.ALERTA
        rotulo = "API conectada" if conectada else "API indisponível"
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:{estilo.ESPACO['sm']}px;
                        font-size:0.82rem">
              <span style="width:7px;height:7px;border-radius:50%;background:{cor};
                           flex-shrink:0"></span>
              <span style="color:#E8EDF5">{rotulo}</span>
            </div>
            <div style="font-size:0.72rem;color:#8FA3BF;margin-top:4px">
              {cliente.base}
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not conectada:
            st.caption("Suba o serviço: `uvicorn src.api.app:app`")

        st.divider()
        st.markdown(
            f"""
            <div style="font-size:0.75rem;color:#8FA3BF;line-height:1.5">
              As recomendações vêm exclusivamente dos procedimentos técnicos da empresa.
              Defeitos sem procedimento cadastrado não recebem recomendação.
            </div>
            """,
            unsafe_allow_html=True,
        )

    return escolha


def main() -> None:
    estilo.aplicar()
    cliente = ClienteApi()
    PAGINAS[_barra_lateral(cliente)](cliente)


if __name__ == "__main__":
    main()
