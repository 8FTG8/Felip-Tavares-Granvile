"""Painel do histórico monitorado."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.cliente import ApiIndisponivel, ClienteApi
from app.componentes import aviso_api_indisponivel

#: Cores por situação documental. A cobertura é o que o painel precisa comunicar antes de
#: qualquer outra coisa: um defeito frequente e sem procedimento é a lacuna mais cara da
#: operação.
COR_DOCUMENTADA = "#2E7D32"
COR_SEM_DOCUMENTO = "#C62828"
COR_ESTADO = "#78909C"


def _cor(condicao: dict) -> str:
    if condicao["tipo_condicao"] != "defeito":
        return COR_ESTADO
    return COR_DOCUMENTADA if condicao["documentada"] else COR_SEM_DOCUMENTO


def renderizar(cliente: ClienteApi) -> None:
    st.title("Painel do histórico")
    st.caption(
        "Panorama dos eventos monitorados e da cobertura documental por tipo de defeito."
    )

    try:
        dados = cliente.estatisticas()
    except ApiIndisponivel:
        aviso_api_indisponivel()
        return

    resumo = dados["resumo"]
    condicoes = pd.DataFrame(dados["condicoes"])

    colunas = st.columns(4)
    colunas[0].metric("Eventos monitorados", f"{resumo['total_eventos']:,}".replace(",", "."))
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

    st.caption(
        f"Janela monitorada: {resumo['primeiro_evento'][:10]} a "
        f"{resumo['ultimo_evento'][:10]} · {resumo['dias_com_registro']} dias com registro"
    )

    st.divider()

    st.subheader("Ocorrências por condição")
    defeitos = condicoes[condicoes["tipo_condicao"] == "defeito"].copy()
    defeitos["situacao"] = defeitos["documentada"].map(
        {True: "Com procedimento", False: "Sem procedimento"}
    )
    figura = px.bar(
        defeitos.sort_values("eventos"),
        x="eventos",
        y="condicao",
        color="situacao",
        orientation="h",
        color_discrete_map={
            "Com procedimento": COR_DOCUMENTADA,
            "Sem procedimento": COR_SEM_DOCUMENTO,
        },
        labels={"eventos": "eventos", "condicao": "", "situacao": ""},
    )
    figura.update_layout(height=420, legend={"orientation": "h", "y": 1.12})
    st.plotly_chart(figura, use_container_width=True)

    sem_documento = defeitos[~defeitos["documentada"]]
    if not sem_documento.empty:
        total = int(sem_documento["eventos"].sum())
        nomes = ", ".join(f"`{c}`" for c in sem_documento["condicao"])
        st.warning(
            f"**{total:,}".replace(",", ".")
            + f" eventos sem procedimento cadastrado** ({nomes}). "
            "Para esses defeitos o sistema não emite recomendação — cadastre o "
            "procedimento na aba *Documentos*."
        )

    st.divider()

    esquerda, direita = st.columns([3, 2])

    with esquerda:
        st.subheader("Eventos ao longo do tempo")
        serie = pd.DataFrame(
            {
                "dia": pd.to_datetime(list(dados["eventos_por_dia"].keys())),
                "eventos": list(dados["eventos_por_dia"].values()),
            }
        ).sort_values("dia")
        linha = px.area(serie, x="dia", y="eventos", labels={"dia": "", "eventos": ""})
        linha.update_traces(line_color="#1565C0", fillcolor="rgba(21,101,192,0.15)")
        linha.update_layout(height=300)
        st.plotly_chart(linha, use_container_width=True)
        st.caption(
            "Os defeitos foram coletados em janelas temporais quase disjuntas — cada "
            "campanha de ensaio concentra um modo de falha. É por isso que a data não "
            "entra como atributo do modelo: ela prediz o rótulo por construção."
        )

    with direita:
        st.subheader("Rotação")
        rpm = pd.DataFrame(
            {
                "rpm": list(dados["eventos_por_rpm"].keys()),
                "eventos": list(dados["eventos_por_rpm"].values()),
            }
        )
        barras = px.bar(rpm, x="rpm", y="eventos", labels={"rpm": "rpm", "eventos": ""})
        barras.update_traces(marker_color="#455A64")
        barras.update_layout(height=300)
        st.plotly_chart(barras, use_container_width=True)
        st.caption(
            "Cinco rotações distintas em todo o histórico: são campanhas de bancada, não "
            "operação contínua."
        )

    st.divider()

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
            "% do total": st.column_config.NumberColumn(format="%.2f%%"),
            "eventos/dia": st.column_config.NumberColumn(format="%.0f"),
        },
    )
