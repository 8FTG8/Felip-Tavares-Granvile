"""Análise de um evento de sensor."""

from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import streamlit as st

from app import estilo
from app.cliente import ApiIndisponivel, ClienteApi
from app.componentes import aviso_api_indisponivel, mostrar_fontes, rodape_modelo, selo_caminho

#: Evento do enunciado, disponível como ponto de partida da demonstração.
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

#: Casos preparados para a demonstração, um por caminho de resposta (ADR-006).
CASOS = {
    "Defeito com procedimento (cocked_rotor)": "cocked_rotor_2",
    "Defeito sem procedimento (falta_fase)": "new_falta_fase_0",
    "Documentação apenas adjacente (eccentric_rotor)": "eccentric_rotor_2",
    "Estado do sistema (normal)": "normal_2",
}


def _mostrar_contexto(contexto: dict) -> None:
    st.subheader("Ocorrências semelhantes no histórico")

    colunas = st.columns(3)
    colunas[0].metric(
        "Eventos similares",
        f"{contexto['total_ocorrencias_similares']:,}".replace(",", "."),
        help="Total histórico das condições presentes na vizinhança do evento.",
    )
    colunas[1].metric("Vizinhos analisados", len(contexto["vizinhos"]))
    colunas[2].metric(
        "Similaridade máxima", f"{contexto['contexto_operacional'].get('similaridade_maxima', 0):.3f}"
    )

    resumo = pd.DataFrame(contexto["ocorrencias_por_condicao"])
    if not resumo.empty:
        st.dataframe(
            resumo[
                ["condicao", "vizinhos", "ocorrencias_historicas", "frequencia_diaria",
                 "primeira", "ultima"]
            ].rename(
                columns={
                    "condicao": "condição",
                    "vizinhos": "vizinhos",
                    "ocorrencias_historicas": "ocorrências no histórico",
                    "frequencia_diaria": "eventos/dia",
                    "primeira": "primeira",
                    "ultima": "última",
                }
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "eventos/dia": st.column_config.NumberColumn(format="%.0f"),
                "primeira": st.column_config.DatetimeColumn(format="DD/MM/YYYY"),
                "última": st.column_config.DatetimeColumn(format="DD/MM/YYYY"),
            },
        )

        if len(resumo) > 1:
            st.info(
                "**Os vizinhos mais próximos pertencem a famílias diferentes.** A "
                "assinatura vibratória agregada não separa esses modos de falha — "
                "distingui-los exigiria análise espectral de envelope, que estas métricas "
                "não trazem. É por isso que o sistema usa o rótulo anotado pelo operador "
                "em vez de inferir o defeito a partir dos sensores."
            )

    with st.expander("Vizinhos individuais", expanded=False):
        vizinhos = pd.DataFrame(contexto["vizinhos"])
        st.dataframe(
            vizinhos[["id", "created_at", "condicao", "rotulo_bruto", "rpm", "similaridade"]]
            .rename(
                columns={
                    "created_at": "registrado em",
                    "condicao": "condição",
                    "rotulo_bruto": "anotação do operador",
                    "similaridade": "similaridade",
                }
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "registrado em": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                "similaridade": st.column_config.ProgressColumn(
                    min_value=0.0, max_value=1.0, format="%.3f"
                ),
            },
        )

    distribuicao = contexto.get("distribuicao_temporal") or {}
    if distribuicao:
        st.markdown("**Distribuição ao longo do tempo**")
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
        estilo.aplicar_layout(figura, altura=240)
        st.plotly_chart(figura, use_container_width=True)


def renderizar(cliente: ClienteApi) -> None:
    estilo.cabecalho(
        "Análise de evento",
        "Recebe a leitura de um sensor, localiza ocorrências semelhantes no histórico e "
        "prescreve a ação corretiva quando há procedimento que a fundamente.",
    )

    caso = st.selectbox("Caso de demonstração", list(CASOS))
    evento_base = dict(EVENTO_EXEMPLO, fault=CASOS[caso])

    with st.expander("Evento em JSON (editável)", expanded=False):
        texto = st.text_area(
            "Conteúdo enviado à API",
            value=json.dumps(evento_base, indent=2, ensure_ascii=False),
            height=280,
            label_visibility="collapsed",
        )

    pergunta = st.text_input(
        "Pergunta específica (opcional)",
        placeholder="ex.: o eixo pode estar empenado?",
    )

    if not st.button("Analisar evento", type="primary"):
        return

    try:
        evento = json.loads(texto)
    except json.JSONDecodeError as erro:
        st.error(f"JSON inválido: {erro}")
        return

    try:
        with st.spinner("Analisando o evento…"):
            resultado = cliente.analisar(evento, pergunta or None)
    except ApiIndisponivel:
        aviso_api_indisponivel()
        return
    except ValueError as erro:
        st.error(f"A API recusou o evento: {erro}")
        return

    st.divider()

    selo_caminho(resultado["caminho"], resultado.get("documento"))
    st.markdown(
        f"<p style='font-size:0.85rem;color:{estilo.TINTA_SECUNDARIA};"
        f"margin-bottom:{estilo.ESPACO['lg']}px'>Condição identificada: "
        f"<b style='color:{estilo.TINTA}'>{resultado['condicao']}</b> · anotada pelo "
        f"operador como <code>{resultado['rotulo_bruto']}</code></p>",
        unsafe_allow_html=True,
    )

    st.markdown(resultado["recomendacao"])
    mostrar_fontes(resultado["fontes"])
    rodape_modelo(resultado.get("modelo"))

    if resultado.get("contexto"):
        st.divider()
        _mostrar_contexto(resultado["contexto"])
