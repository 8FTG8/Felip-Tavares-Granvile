"""Elementos visuais reaproveitados entre as páginas.

A apresentação dos três caminhos de resposta é o ponto sensível: a diferença entre
prescrever, recusar por falta de documento e informar que não há defeito precisa ser
imediata na tela. Um técnico que confunde uma recusa com uma recomendação vazia perde a
informação mais importante que o sistema tem a dar. Por isso cada caminho recebe cor,
ícone **e** rótulo — a cor nunca carrega o significado sozinha.
"""

from __future__ import annotations

import streamlit as st

from app import estilo

#: Aparência de cada caminho de resposta (ADR-006): ícone, título, explicação e cor.
CAMINHOS = {
    "prescricao": ("✓", "Procedimento encontrado", "Recomendação fundamentada em documento técnico", estilo.SUCESSO),
    "sem_documento": ("!", "Sem procedimento cadastrado", "O sistema não emite recomendação sem respaldo documental", estilo.ALERTA),
    "estado": ("·", "Equipamento sem defeito", "O evento registra um estado operacional, não uma falha", estilo.ACENTO),
    "sem_condicao": ("?", "Condição não informada", "Sem a condição, não há como saber qual procedimento responde", estilo.TINTA_SECUNDARIA),
}


def selo_caminho(caminho: str, documento: str | None = None) -> None:
    """Faixa que identifica o caminho de resposta tomado pelo sistema."""
    icone, titulo, descricao, cor = CAMINHOS.get(
        caminho, ("•", caminho, "", estilo.TINTA_SECUNDARIA)
    )
    fonte = (
        f"<span style='margin-left:auto;font-size:0.78rem;color:{estilo.TINTA_SECUNDARIA};"
        f"background:{estilo.SUPERFICIE_ALTERNATIVA};padding:2px 10px;"
        f"border-radius:{estilo.RAIO['cheio']}px'>{documento}</span>"
        if documento
        else ""
    )
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:{estilo.ESPACO['md']}px;
                    background:{estilo.SUPERFICIE};border:1px solid {estilo.BORDA};
                    border-left:3px solid {cor};border-radius:{estilo.RAIO['md']}px;
                    padding:{estilo.ESPACO['md']}px {estilo.ESPACO['lg']}px;
                    margin-bottom:{estilo.ESPACO['lg']}px;
                    box-shadow:0 1px 4px rgba(0,0,0,0.03)">
          <span style="display:flex;align-items:center;justify-content:center;
                       width:26px;height:26px;border-radius:{estilo.RAIO['cheio']}px;
                       background:{cor}1A;color:{cor};font-weight:700;flex-shrink:0">{icone}</span>
          <span>
            <span style="font-weight:600;color:{estilo.TINTA}">{titulo}</span><br>
            <span style="font-size:0.82rem;color:{estilo.TINTA_SECUNDARIA}">{descricao}</span>
          </span>
          {fonte}
        </div>
        """,
        unsafe_allow_html=True,
    )


def mostrar_fontes(fontes: list[dict]) -> None:
    """Exibe as seções que fundamentam a recomendação.

    A rastreabilidade é requisito, não enfeite: o técnico precisa poder abrir o
    procedimento citado e conferir. Documentos transcritos por OCR são marcados, porque o
    reconhecimento pode conter ruído.
    """
    if not fontes:
        return

    with st.expander(f"Fontes citadas ({len(fontes)})", expanded=False):
        for fonte in fontes:
            marca = (
                f" · <span style='color:{estilo.ALERTA}'>transcrito por OCR</span>"
                if fonte.get("origem") == "ocr"
                else ""
            )
            st.markdown(
                f"""
                <div style="padding:{estilo.ESPACO['sm']}px 0;
                            border-bottom:1px solid {estilo.BORDA}">
                  <span style="font-weight:600;color:{estilo.TINTA}">
                    {fonte['documento']}, seção {fonte['numero_secao']}
                  </span>
                  <span style="color:{estilo.TINTA_SECUNDARIA}"> — {fonte['titulo_secao']}</span><br>
                  <span style="font-size:0.78rem;color:{estilo.TINTA_SUAVE}">
                    relevância {fonte['relevancia']:.3f}{marca}
                  </span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def aviso_api_indisponivel() -> None:
    st.error(
        "**A API não está respondendo.**\n\n"
        "A interface é apenas um cliente do serviço — em ambiente industrial o consumidor "
        "principal seria o supervisório. Suba a API antes de continuar:\n\n"
        "```\nuvicorn src.api.app:app\n```"
    )


def rodape_modelo(modelo: str | None) -> None:
    texto = (
        f"Resposta redigida por <code>{modelo}</code> a partir dos trechos citados."
        if modelo
        else "Resposta composta pelo sistema, sem geração por modelo de linguagem."
    )
    st.markdown(
        f"<p style='font-size:0.78rem;color:{estilo.TINTA_SUAVE};margin-top:{estilo.ESPACO['sm']}px'>"
        f"{texto}</p>",
        unsafe_allow_html=True,
    )
