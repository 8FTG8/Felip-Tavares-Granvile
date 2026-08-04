"""Cadastro de procedimentos e situação da base documental."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import estilo
from app.cliente import ApiIndisponivel, ClienteApi
from app.componentes import aviso_api_indisponivel


def renderizar(cliente: ClienteApi) -> None:
    estilo.cabecalho(
        "Base documental",
        "Quando um defeito não tem procedimento cadastrado, o sistema recusa-se a "
        "recomendar. Cadastrar o procedimento aqui faz o defeito passar a ser atendido "
        "imediatamente, sem reiniciar o serviço.",
    )

    try:
        cobertura = cliente.cobertura()
    except ApiIndisponivel:
        aviso_api_indisponivel()
        return

    situacoes = pd.DataFrame(cobertura)
    pendentes = situacoes[~situacoes["documentada"]]

    colunas = st.columns(3)
    colunas[0].metric("Famílias de defeito", len(situacoes))
    colunas[1].metric("Com procedimento", int(situacoes["documentada"].sum()))
    colunas[2].metric("Aguardando cadastro", len(pendentes))

    st.divider()

    st.subheader("Situação por defeito")
    for _, situacao in situacoes.iterrows():
        documentada = bool(situacao["documentada"])
        cor = estilo.SUCESSO if documentada else estilo.ALERTA
        if documentada:
            origem = (
                " · cadastrado em operação" if situacao["cadastrado_em_operacao"] else ""
            )
            detalhe = (
                f"<code>{situacao['documento']}</code>"
                f"<span style='color:{estilo.TINTA_SUAVE}'>{origem}</span>"
            )
        else:
            detalhe = (
                f"<span style='color:{estilo.TINTA_SECUNDARIA}'>"
                f"{situacao['justificativa']}</span>"
            )

        st.markdown(
            f"""
            <div style="display:flex;gap:{estilo.ESPACO['md']}px;
                        background:{estilo.SUPERFICIE};border:1px solid {estilo.BORDA};
                        border-left:3px solid {cor};
                        border-radius:{estilo.RAIO['md']}px;
                        padding:{estilo.ESPACO['md']}px {estilo.ESPACO['lg']}px;
                        margin-bottom:{estilo.ESPACO['sm']}px;
                        box-shadow:0 1px 4px rgba(0,0,0,0.03)">
              <span style="color:{cor};font-weight:700;flex-shrink:0">
                {"✓" if documentada else "!"}
              </span>
              <span style="font-size:0.88rem;line-height:1.5">
                <b style="color:{estilo.TINTA}">{situacao['condicao']}</b><br>{detalhe}
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    st.subheader("Cadastrar procedimento")
    st.caption(
        "O documento passa pelo mesmo tratamento da base original: extração de texto, "
        "fatiamento por seção numerada e indexação. PDFs digitalizados são reconhecidos "
        "por OCR."
    )

    opcoes = sorted(pendentes["condicao"].tolist()) or sorted(situacoes["condicao"].tolist())
    condicao = st.selectbox("Defeito que o procedimento cobre", opcoes)

    arquivo = st.file_uploader("Procedimento técnico (PDF)", type=["pdf"])

    if not st.button("Cadastrar", type="primary", disabled=arquivo is None):
        return

    try:
        with st.spinner("Extraindo, fatiando e indexando o documento…"):
            resultado = cliente.cadastrar_documento(
                condicao, arquivo.name, arquivo.getvalue()
            )
    except ApiIndisponivel:
        aviso_api_indisponivel()
        return
    except ValueError as erro:
        st.error(f"Cadastro recusado: {erro}")
        return

    origem = "transcrito por OCR" if resultado["origem"] == "ocr" else "texto nativo"
    st.success(
        f"**{resultado['condicao']}** passa a ser atendido por `{resultado['documento']}` "
        f"— {resultado['trechos']} seções indexadas ({origem})."
    )
    with st.expander("Seções reconhecidas", expanded=False):
        for secao in resultado["secoes"]:
            st.markdown(f"- {secao}")

    st.info(
        "Consulte novamente um evento com esta condição: a recusa foi substituída por "
        "prescrição fundamentada no documento recém-cadastrado."
    )
