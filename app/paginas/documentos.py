"""Cadastro de procedimentos e situação da base documental."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import estilo
from app.cliente import ApiIndisponivel, ClienteApi
from app.componentes import aviso_api_indisponivel


def _linha_cobertura(situacao: pd.Series) -> None:
    """Uma linha por defeito, com pílula de status — padrão de tabela das referências."""
    documentada = bool(situacao["documentada"])
    cor = estilo.SUCESSO if documentada else estilo.ALERTA
    rotulo = "Coberto" if documentada else "Sem procedimento"

    if documentada:
        origem = " · cadastrado em operação" if situacao["cadastrado_em_operacao"] else ""
        detalhe = (
            f"<code style='font-size:0.78rem'>{situacao['documento']}</code>"
            f"<span style='color:{estilo.TINTA_SUAVE};font-size:0.78rem'>{origem}</span>"
        )
    else:
        detalhe = (
            f"<span style='color:{estilo.TINTA_SECUNDARIA};font-size:0.79rem;"
            f"line-height:1.45'>{situacao['justificativa']}</span>"
        )

    st.markdown(
        f"""
        <div style="display:flex;align-items:flex-start;gap:{estilo.ESPACO['md']}px;
                    padding:{estilo.ESPACO['md']}px 0;
                    border-bottom:1px solid {estilo.BORDA}">
          <span style="flex-shrink:0;font-size:0.7rem;font-weight:600;
                       text-transform:uppercase;letter-spacing:0.04em;color:{cor};
                       background:{cor}14;border:1px solid {cor}33;
                       border-radius:{estilo.RAIO['sm']}px;padding:3px 8px;
                       min-width:118px;text-align:center">{rotulo}</span>
          <span style="line-height:1.5">
            <b style="color:{estilo.TINTA};font-size:0.88rem">{situacao['condicao']}</b><br>
            {detalhe}
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _cadastro(cliente: ClienteApi, pendentes: list[str], todas: list[str]) -> None:
    with estilo.cartao("Cadastrar procedimento"):
        st.markdown(
            f"<p style='font-size:0.82rem;color:{estilo.TINTA_SECUNDARIA};"
            f"margin-bottom:{estilo.ESPACO['md']}px;line-height:1.5'>"
            "O documento passa pelo mesmo tratamento da base original: extração de texto, "
            "fatiamento por seção numerada e indexação. PDFs digitalizados são "
            "reconhecidos por OCR.</p>",
            unsafe_allow_html=True,
        )

        condicao = st.selectbox(
            "Defeito que o procedimento cobre", sorted(pendentes) or sorted(todas)
        )
        arquivo = st.file_uploader("Procedimento técnico (PDF)", type=["pdf"])

        if not st.button(
            "Cadastrar",
            type="primary",
            disabled=arquivo is None,
            use_container_width=True,
            icon=":material/upload_file:",
        ):
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
            f"**{resultado['condicao']}** passa a ser atendido por "
            f"`{resultado['documento']}` — {resultado['trechos']} seções indexadas "
            f"({origem})."
        )
        with st.expander("Seções reconhecidas", expanded=False):
            for secao in resultado["secoes"]:
                st.markdown(f"- {secao}")
        st.info(
            "Volte à **Análise de evento** e consulte um evento desta condição: a recusa "
            "foi substituída por prescrição fundamentada no documento recém-cadastrado."
        )


def renderizar(cliente: ClienteApi) -> None:
    try:
        cobertura = cliente.cobertura()
        sistema = cliente.sistema()
    except ApiIndisponivel:
        estilo.topo("Base documental", "Procedimentos técnicos e cobertura por defeito.")
        aviso_api_indisponivel()
        return

    situacoes = pd.DataFrame(cobertura)
    pendentes = situacoes[~situacoes["documentada"]]["condicao"].tolist()

    estilo.topo(
        "Base documental",
        "Defeito sem procedimento não recebe recomendação. Cadastrar aqui faz o sistema "
        "passar a atendê-lo imediatamente, sem reiniciar o serviço.",
        etiquetas=(
            estilo.chip(
                f"{sistema['familias_documentadas']}/{sistema['familias_totais']} famílias"
            ),
            estilo.chip(f"{sistema['trechos_indexados']} seções indexadas"),
        ),
    )

    lista, formulario = st.columns([3, 2])

    with lista, estilo.cartao(
        "Situação por defeito", f"{len(pendentes)} aguardando cadastro"
    ):
        for _, situacao in situacoes.iterrows():
            _linha_cobertura(situacao)

    with formulario:
        _cadastro(cliente, pendentes, situacoes["condicao"].tolist())
