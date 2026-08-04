"""Análise de um evento de sensor.

A tela é dividida em entrada à esquerda e resultado à direita. O arranjo serve à
demonstração: trocando o caso, a resposta muda sem que a página se reorganize, e os quatro
caminhos ficam comparáveis lado a lado.
"""

from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from app import estilo
from app.cliente import ApiIndisponivel, ClienteApi
from app.componentes import aviso_api_indisponivel, mostrar_fontes, rodape_modelo, selo_caminho

#: Evento do enunciado, ponto de partida da demonstração.
EVENTO_EXEMPLO = {
    "id": 114387,
    "created_at": "2026-06-01 21:32:53.911176+00:00",
    "z_rms_velocity_mm_s": 1.517,
    "x_rms_velocity_mm_s": 2.0,
    "temperature_c": 24.69,
    "z_peak_acceleration_g": 0.484,
    "x_peak_acceleration_g": 0.631,
    "z_peak_vel_comp_freq_hz": 61.0,
    "x_peak_vel_comp_freq_hz": 61.0,
    "z_rms_acceleration_g": 0.09,
    "x_rms_acceleration_g": 0.114,
    "z_kurtosis": 2.392,
    "x_kurtosis": 2.77,
    "z_crest_factor": 3.747,
    "x_crest_factor": 4.269,
    "z_high_freq_rms_accel_g": 0.129,
    "x_high_freq_rms_accel_g": 0.147,
    "fault": "cocked_rotor_2",
    "rpm": 1000.0,
}

#: Um caso por caminho de resposta (ADR-006), na ordem da demonstração.
CASOS = {
    "Defeito com procedimento — cocked_rotor": "cocked_rotor_2",
    "Defeito sem procedimento — falta_fase": "new_falta_fase_0",
    "Documentação apenas adjacente — eccentric_rotor": "eccentric_rotor_2",
    "Estado do sistema — normal": "normal_2",
}


def _entrada(cliente: ClienteApi) -> None:
    with estilo.cartao("Evento de entrada"):
        caso = st.selectbox("Caso de demonstração", list(CASOS), key="caso_demo")
        evento_base = dict(EVENTO_EXEMPLO, fault=CASOS[caso])

        with st.expander("JSON enviado à API", expanded=False):
            texto = st.text_area(
                "Conteúdo",
                value=json.dumps(evento_base, indent=2, ensure_ascii=False),
                height=260,
                label_visibility="collapsed",
                key=f"json_{caso}",
            )

        pergunta = st.text_input(
            "Pergunta específica (opcional)",
            placeholder="ex.: o eixo pode estar empenado?",
        )

        if not st.button("Analisar evento", type="primary", use_container_width=True):
            return

        try:
            evento = json.loads(texto)
        except json.JSONDecodeError as erro:
            st.session_state.analise_erro = f"JSON inválido: {erro}"
            st.session_state.analise = None
            return

        try:
            with st.spinner("Consultando histórico e procedimentos…"):
                st.session_state.analise = cliente.analisar(evento, pergunta or None)
                st.session_state.analise_erro = None
        except ApiIndisponivel:
            st.session_state.analise_erro = "indisponivel"
            st.session_state.analise = None
        except ValueError as erro:
            st.session_state.analise_erro = f"A API recusou o evento: {erro}"
            st.session_state.analise = None


def _resultado() -> None:
    erro = st.session_state.get("analise_erro")
    resultado = st.session_state.get("analise")

    if erro == "indisponivel":
        aviso_api_indisponivel()
        return
    if erro:
        st.error(erro)
        return

    if not resultado:
        with estilo.cartao():
            st.markdown(
                f"""
                <div style="text-align:center;padding:{estilo.ESPACO['xxl']}px 0;
                            color:{estilo.TINTA_SUAVE}">
                  <span class="material-symbols-outlined"
                        style="font-size:38px;opacity:0.45">vital_signs</span>
                  <p style="margin-top:{estilo.ESPACO['md']}px;font-size:0.88rem">
                    Escolha um caso e acione <b>Analisar evento</b>.<br>
                    A recomendação aparece aqui, com as seções que a fundamentam.
                  </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return

    with estilo.cartao():
        selo_caminho(resultado["caminho"], resultado.get("documento"))
        st.markdown(
            f"<p style='font-size:0.82rem;color:{estilo.TINTA_SECUNDARIA};"
            f"margin:-8px 0 {estilo.ESPACO['lg']}px'>Condição identificada: "
            f"<b style='color:{estilo.TINTA}'>{resultado['condicao']}</b> · anotada pelo "
            f"operador como <code>{resultado['rotulo_bruto']}</code></p>",
            unsafe_allow_html=True,
        )
        st.markdown(resultado["recomendacao"])
        mostrar_fontes(resultado["fontes"])
        rodape_modelo(resultado.get("modelo"))


def _numero(valor: float) -> str:
    return f"{int(valor):,}".replace(",", ".")


def _contexto(contexto: dict) -> None:
    resumo = pd.DataFrame(contexto["ocorrencias_por_condicao"])

    with estilo.cartao(
        "Ocorrências semelhantes no histórico",
        f"{_numero(contexto['total_ocorrencias_similares'])} eventos",
    ):
        vizinhanca, temporal = st.columns([3, 2])

        with vizinhanca:
            if not resumo.empty:
                for _, linha in resumo.iterrows():
                    proporcao = linha["vizinhos"] / max(len(contexto["vizinhos"]), 1)
                    st.markdown(
                        f"""
                        <div style="padding:8px 0;border-bottom:1px solid {estilo.BORDA}">
                          <div style="display:flex;align-items:center;gap:8px">
                            <span style="font-size:0.86rem;font-weight:600;
                                         color:{estilo.TINTA}">{linha['condicao']}</span>
                            <span style="font-size:0.74rem;color:{estilo.TINTA_SUAVE}">
                              {linha['vizinhos']} de {len(contexto['vizinhos'])} vizinhos
                            </span>
                            <span style="margin-left:auto;font-size:0.82rem;
                                         color:{estilo.TINTA_SECUNDARIA}">
                              {_numero(linha['ocorrencias_historicas'])} no histórico ·
                              {linha['frequencia_diaria']:.0f}/dia
                            </span>
                          </div>
                          <div style="height:4px;border-radius:2px;
                                      background:{estilo.SUPERFICIE_ATIVA};margin-top:6px">
                            <div style="width:{proporcao:.0%};height:100%;border-radius:2px;
                                        background:{estilo.ACENTO}"></div>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                if len(resumo) > 1:
                    st.markdown(
                        f"""
                        <div style="background:{estilo.SUPERFICIE_ALTERNATIVA};
                                    border-left:3px solid {estilo.ACENTO};
                                    border-radius:{estilo.RAIO['sm']}px;
                                    padding:{estilo.ESPACO['md']}px;
                                    margin-top:{estilo.ESPACO['md']}px;
                                    font-size:0.8rem;color:{estilo.TINTA_SECUNDARIA};
                                    line-height:1.55">
                          <b style="color:{estilo.TINTA}">Os vizinhos mais próximos
                          pertencem a famílias diferentes.</b> A assinatura vibratória
                          agregada não separa esses modos de falha — distingui-los exigiria
                          análise espectral de envelope, que estas métricas não trazem. É
                          por isso que o sistema usa o rótulo anotado pelo operador em vez
                          de inferir o defeito a partir dos sensores.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        with temporal:
            distribuicao = contexto.get("distribuicao_temporal") or {}
            if distribuicao:
                serie = pd.DataFrame(
                    {
                        "dia": pd.to_datetime(list(distribuicao.keys())),
                        "eventos": list(distribuicao.values()),
                    }
                ).sort_values("dia")
                figura = px.bar(serie, x="dia", y="eventos", labels={"dia": "", "eventos": ""})
                figura.update_traces(
                    marker_color=estilo.ACENTO,
                    marker_line_width=2,
                    marker_line_color=estilo.SUPERFICIE,
                    hovertemplate="<b>%{x|%d/%m/%Y}</b><br>%{y:,} eventos<extra></extra>",
                )
                estilo.aplicar_layout(figura, altura=220)
                st.plotly_chart(figura, use_container_width=True)
                st.markdown(
                    f"<p style='font-size:0.74rem;color:{estilo.TINTA_SUAVE}'>"
                    "Distribuição ao longo do tempo das condições presentes na "
                    "vizinhança.</p>",
                    unsafe_allow_html=True,
                )

        with st.expander("Vizinhos individuais", expanded=False):
            vizinhos = pd.DataFrame(contexto["vizinhos"])
            st.dataframe(
                vizinhos[
                    ["id", "created_at", "condicao", "rotulo_bruto", "rpm", "similaridade"]
                ].rename(
                    columns={
                        "created_at": "registrado em",
                        "condicao": "condição",
                        "rotulo_bruto": "anotação do operador",
                    }
                ),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "registrado em": st.column_config.DatetimeColumn(
                        format="DD/MM/YYYY HH:mm"
                    ),
                    "similaridade": st.column_config.ProgressColumn(
                        min_value=0.0, max_value=1.0, format="%.3f"
                    ),
                },
            )


def renderizar(cliente: ClienteApi) -> None:
    etiquetas: tuple[str, ...] = ()
    try:
        sistema = cliente.sistema()
        etiquetas = (
            estilo.chip(sistema["modelo"], estilo.SUCESSO, icone="ponto"),
            estilo.chip(f"limiar {sistema['limiar_relevancia']:.3f}"),
        )
    except ApiIndisponivel:
        pass

    estilo.topo(
        "Análise de evento",
        "Localiza ocorrências semelhantes no histórico e prescreve a ação corretiva "
        "quando há procedimento que a fundamente.",
        etiquetas=etiquetas,
    )

    entrada, resultado = st.columns([2, 3])
    with entrada:
        _entrada(cliente)
    with resultado:
        _resultado()

    analise = st.session_state.get("analise")
    if analise and analise.get("contexto"):
        st.write("")
        _contexto(analise["contexto"])
