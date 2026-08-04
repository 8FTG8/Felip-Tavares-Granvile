"""Painel do histórico monitorado."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app import estilo
from app.cliente import ApiIndisponivel, ClienteApi
from app.componentes import aviso_api_indisponivel

#: A cobertura documental é um estado, não uma categoria — usa a paleta de status. As
#: cores foram verificadas quanto a separação sob daltonismo; ainda assim os valores
#: aparecem rotulados no próprio gráfico, porque o contraste com o fundo fica abaixo de
#: 3:1 e a cor não pode ser o único portador da informação.
SITUACAO = {"Com procedimento": estilo.SUCESSO, "Sem procedimento": estilo.ALERTA}


def _metricas(resumo: dict) -> None:
    colunas = st.columns(4)
    colunas[0].metric(
        "Eventos monitorados", f"{resumo['total_eventos']:,}".replace(",", ".")
    )
    colunas[1].metric("Defeitos", f"{resumo['total_defeitos']:,}".replace(",", "."))
    colunas[2].metric("Famílias de defeito", resumo["familias_de_defeito"])
    colunas[3].metric(
        "Cobertura documental",
        f"{resumo['cobertura_documental']:.1%}",
        help=(
            "Proporção dos eventos de defeito com procedimento cadastrado. Medida em "
            "eventos, não em famílias: é o que informa o alcance real da documentação."
        ),
    )


def _grafico_cobertura(defeitos: pd.DataFrame) -> None:
    dados = defeitos.sort_values("eventos").copy()
    dados["situacao"] = dados["documentada"].map(
        {True: "Com procedimento", False: "Sem procedimento"}
    )
    dados["rotulo"] = dados["eventos"].map(lambda v: f"{v:,}".replace(",", "."))

    figura = px.bar(
        dados,
        x="eventos",
        y="condicao",
        color="situacao",
        orientation="h",
        text="rotulo",
        color_discrete_map=SITUACAO,
        labels={"eventos": "", "condicao": "", "situacao": ""},
        custom_data=["situacao", "documento"],
    )
    figura.update_traces(
        marker_line_width=2,
        marker_line_color=estilo.SUPERFICIE,
        textposition="outside",
        textfont={"size": 11, "color": estilo.TINTA_SECUNDARIA},
        cliponaxis=False,
        hovertemplate=(
            "<b>%{y}</b><br>%{x:,} eventos<br>%{customdata[0]}<extra></extra>"
        ),
    )
    estilo.aplicar_layout(figura, altura=420)
    figura.update_xaxes(showgrid=False, showticklabels=False)
    figura.update_yaxes(showgrid=False)
    st.plotly_chart(figura, use_container_width=True)


def _alerta_lacuna(defeitos: pd.DataFrame) -> None:
    pendentes = defeitos[~defeitos["documentada"]]
    if pendentes.empty:
        return

    total = f"{int(pendentes['eventos'].sum()):,}".replace(",", ".")
    itens = "".join(
        f"<li style='margin-bottom:2px'><b>{linha['condicao']}</b> — "
        f"{linha['eventos']:,}".replace(",", ".") + " eventos</li>"
        for _, linha in pendentes.sort_values("eventos", ascending=False).iterrows()
    )
    st.markdown(
        f"""
        <div style="background:{estilo.SUPERFICIE};border:1px solid {estilo.BORDA};
                    border-left:3px solid {estilo.ALERTA};
                    border-radius:{estilo.RAIO['md']}px;
                    padding:{estilo.ESPACO['lg']}px;margin-top:{estilo.ESPACO['sm']}px;
                    box-shadow:0 1px 4px rgba(0,0,0,0.03)">
          <div style="font-weight:600;color:{estilo.TINTA};
                      margin-bottom:{estilo.ESPACO['sm']}px">
            {total} eventos sem procedimento cadastrado
          </div>
          <ul style="margin:0 0 {estilo.ESPACO['sm']}px 0;padding-left:18px;
                     color:{estilo.TINTA_SECUNDARIA};font-size:0.88rem">{itens}</ul>
          <div style="font-size:0.82rem;color:{estilo.TINTA_SECUNDARIA}">
            Para esses defeitos o sistema não emite recomendação. Cadastre o procedimento
            na aba <b>Base documental</b>.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _series_temporais(dados: dict) -> None:
    esquerda, direita = st.columns([3, 2])

    with esquerda:
        st.subheader("Eventos ao longo do tempo")
        serie = pd.DataFrame(
            {
                "dia": pd.to_datetime(list(dados["eventos_por_dia"].keys())),
                "eventos": list(dados["eventos_por_dia"].values()),
            }
        ).sort_values("dia")

        figura = px.area(serie, x="dia", y="eventos", labels={"dia": "", "eventos": ""})
        figura.update_traces(
            line={"color": estilo.ACENTO, "width": 2},
            fillcolor="rgba(3,105,161,0.10)",
            hovertemplate="<b>%{x|%d/%m/%Y}</b><br>%{y:,} eventos<extra></extra>",
        )
        estilo.aplicar_layout(figura, altura=300)
        figura.update_layout(hovermode="x unified")
        st.plotly_chart(figura, use_container_width=True)
        st.caption(
            "Cada campanha de ensaio concentra um modo de falha, em janelas quase "
            "disjuntas. É por isso que a data não entra como atributo do modelo: ela "
            "prediz o rótulo por construção."
        )

    with direita:
        st.subheader("Rotação")
        rpm = pd.DataFrame(
            {
                "rpm": list(dados["eventos_por_rpm"].keys()),
                "eventos": list(dados["eventos_por_rpm"].values()),
            }
        )
        figura = px.bar(rpm, x="rpm", y="eventos", labels={"rpm": "rpm", "eventos": ""})
        figura.update_traces(
            marker_color=estilo.ACENTO,
            marker_line_width=2,
            marker_line_color=estilo.SUPERFICIE,
            hovertemplate="<b>%{x} rpm</b><br>%{y:,} eventos<extra></extra>",
        )
        estilo.aplicar_layout(figura, altura=300)
        st.plotly_chart(figura, use_container_width=True)
        st.caption(
            "Cinco rotações distintas em todo o histórico: são campanhas de bancada, "
            "não operação contínua."
        )


def _tabela(condicoes: pd.DataFrame) -> None:
    st.subheader("Detalhamento por condição")
    st.caption(
        "A coluna *grafias* mostra de quantas formas diferentes o operador anotou a mesma "
        "condição. A normalização canônica reduz as 151 anotações do histórico às 17 "
        "condições reais."
    )
    tabela = condicoes[
        [
            "condicao",
            "tipo_condicao",
            "eventos",
            "proporcao",
            "rotulos_brutos",
            "frequencia_diaria",
            "documento",
        ]
    ].rename(
        columns={
            "condicao": "condição",
            "tipo_condicao": "tipo",
            "proporcao": "% do total",
            "rotulos_brutos": "grafias",
            "frequencia_diaria": "eventos/dia",
            "documento": "procedimento",
        }
    )
    st.dataframe(
        tabela,
        use_container_width=True,
        hide_index=True,
        column_config={
            "eventos": st.column_config.NumberColumn(format="%d"),
            "% do total": st.column_config.NumberColumn(format="%.2f%%"),
            "eventos/dia": st.column_config.NumberColumn(format="%.0f"),
        },
    )


def renderizar(cliente: ClienteApi) -> None:
    estilo.cabecalho(
        "Painel do histórico",
        "Panorama dos eventos monitorados e da cobertura documental por tipo de defeito.",
    )

    try:
        dados = cliente.estatisticas()
    except ApiIndisponivel:
        aviso_api_indisponivel()
        return

    resumo = dados["resumo"]
    condicoes = pd.DataFrame(dados["condicoes"])

    _metricas(resumo)
    st.markdown(
        f"<p style='font-size:0.8rem;color:{estilo.TINTA_SUAVE};"
        f"margin-top:{estilo.ESPACO['sm']}px'>"
        f"Janela monitorada: {resumo['primeiro_evento'][:10]} a "
        f"{resumo['ultimo_evento'][:10]} · {resumo['dias_com_registro']} dias com registro"
        f"</p>",
        unsafe_allow_html=True,
    )

    st.divider()
    st.subheader("Ocorrências por condição")
    defeitos = condicoes[condicoes["tipo_condicao"] == "defeito"].copy()
    _grafico_cobertura(defeitos)
    _alerta_lacuna(defeitos)

    st.divider()
    _series_temporais(dados)

    st.divider()
    _tabela(condicoes)
