"""Elementos visuais reaproveitados entre as páginas da interface.

A apresentação dos três caminhos de resposta é o ponto sensível: a diferença entre
prescrever, recusar por falta de documento e informar que não há defeito precisa ser
imediata na tela. Um técnico que confunde uma recusa com uma recomendação vazia perde a
informação mais importante que o sistema tem a dar.
"""

from __future__ import annotations

import streamlit as st

#: Cada caminho recebe cor, ícone e rótulo próprios (ADR-006).
APARENCIA = {
    "prescricao": ("✅", "Procedimento encontrado", "success"),
    "sem_documento": ("⚠️", "Sem procedimento cadastrado", "warning"),
    "estado": ("ℹ️", "Equipamento sem defeito", "info"),
    "sem_condicao": ("❓", "Condição não informada", "info"),
}


def selo_caminho(caminho: str, documento: str | None = None) -> None:
    icone, rotulo, estilo = APARENCIA.get(caminho, ("•", caminho, "info"))
    texto = f"{icone}  **{rotulo}**"
    if documento:
        texto += f" — fonte: `{documento}`"
    getattr(st, estilo)(texto)


def mostrar_fontes(fontes: list[dict]) -> None:
    """Exibe as seções que fundamentam a recomendação.

    A rastreabilidade é requisito, não enfeite: o técnico precisa poder abrir o
    procedimento citado e conferir. Documentos processados por OCR são marcados, porque a
    transcrição pode conter ruído de reconhecimento.
    """
    if not fontes:
        return

    with st.expander(f"Fontes citadas ({len(fontes)})", expanded=False):
        for fonte in fontes:
            marca = " · transcrito por OCR" if fonte.get("origem") == "ocr" else ""
            st.markdown(
                f"**{fonte['documento']}, seção {fonte['numero_secao']}** — "
                f"{fonte['titulo_secao']}  \n"
                f"<small>relevância {fonte['relevancia']:.3f}{marca}</small>",
                unsafe_allow_html=True,
            )


def aviso_api_indisponivel() -> None:
    st.error(
        "**A API não está respondendo.**\n\n"
        "A interface é apenas um cliente do serviço — em ambiente industrial o consumidor "
        "principal seria o supervisório. Suba a API antes de continuar:\n\n"
        "```\nuvicorn src.api.app:app --reload\n```"
    )


def rodape_modelo(modelo: str | None) -> None:
    if modelo:
        st.caption(f"Resposta gerada por `{modelo}`, a partir dos trechos citados.")
    else:
        st.caption("Resposta composta pelo sistema, sem geração por modelo de linguagem.")
