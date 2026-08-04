"""Painel do histórico monitorado."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app import estilo
from app.cliente import ApiIndisponivel, ClienteApi
from app.componentes import aviso_api_indisponivel

#: A cobertura documental é um estado, não uma categoria — usa a paleta de status. As
#: cores foram verificadas quanto à separação sob daltonismo; ainda assim os valores
#: aparecem rotulados no gráfico e repetidos na legenda, porque o par âmbar/verde fica na
#: faixa que só é admissível com codificação secundária.
SITUACAO = {"Com procedimento": estilo.SUCESSO, "Sem procedimento": estilo.ALERTA}

INDICADORES = (
    ("Eventos monitorados", "total_eventos", "database"),
    ("Defeitos", "total_defeitos", "warning"),
    ("Famílias de defeito", "familias_de_defeito", "category"),
)


def _numero(valor: float) -> str:
    return f"{int(valor):,}".replace(",", ".")


def _indicadores(resumo: dict) -> None:
    colunas = st.columns(4)

    for coluna, (rotulo, chave, icone) in zip(colunas, INDICADORES):
        with coluna, st.container(border=True):
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:7px;
                            color:{estilo.TINTA_SECUNDARIA};font-size:0.78rem;
                            font-weight:500">
                  <span class="material-symbols-outlined"
                        style="font-size:17px">{icone}</span>{rotulo}
                </div>
                <div style="font-size:1.7rem;font-weight:600;color:{estilo.TINTA};
                            letter-spacing:-0.02em;margin-top:4px">
                  {_numero(resumo[chave])}
                </div>
                """,
                unsafe_allow_html=True,
            )

    cobertura = resumo["cobertura_documental"]
    with colunas[3], st.container(border=True):
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:7px;
                        color:{estilo.TINTA_SECUNDARIA};font-size:0.78rem;
                        font-weight:500">
              <span class="material-symbols-outlined"
                    style="font-size:17px">verified</span>Cobertura documental
            </div>
            <div style="font-size:1.7rem;font-weight:600;color:{estilo.TINTA};
                        letter-spacing:-0.02em;margin-top:4px">{cobertura:.1%}</div>
            <div style="height:5px;border-radius:3px;background:{estilo.BORDA};
                        margin-top:9px;overflow:hidden">
              <div style="width:{cobertura:.1%};height:100%;background:{estilo.SUCESSO}">
              </div>
            </div>
            <div style="font-size:0.72rem;color:{estilo.TINTA_SUAVE};margin-top:5px">
              dos eventos de defeito
            </div>
            """,
            unsafe_allow_html=True,
        )


def _cobertura(defeitos: pd.DataFrame) -> None:
    """Gráfico à esquerda, legenda com contagens à direita.

    A legenda em lista carrega o número junto do nome, o que dá a leitura exata sem
    depender de encostar o cursor — e serve de codificação secundária para a cor.
    """
    dados = defeitos.sort_values("eventos").copy()
    dados["situacao"] = dados["documentada"].map(
        {True: "Com procedimento", False: "Sem procedimento"}
    )

    grafico, legenda = st.columns([3, 2])

    with grafico:
        figura = px.bar(
            dados,
            x="eventos",
            y="condicao",
            color="situacao",
            orientation="h",
            text=dados["eventos"].map(_numero),
            color_discrete_map=SITUACAO,
            labels={"eventos": "", "condicao": "", "situacao": ""},
            custom_data=["situacao"],
        )
        figura.update_traces(
            marker_line_width=2,
            marker_line_color=estilo.SUPERFICIE,
            textposition="outside",
            textfont={"size": 10, "color": estilo.TINTA_SUAVE},
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{x:,} eventos<br>%{customdata[0]}<extra></extra>",
        )
        estilo.aplicar_layout(figura, altura=430)
        figura.update_layout(showlegend=False, margin={"l": 0, "r": 40, "t": 4, "b": 4})
        figura.update_xaxes(showgrid=False, showticklabels=False)
        figura.update_yaxes(showgrid=False, tickfont={"size": 11})
        st.plotly_chart(figura, use_container_width=True)

    with legenda:
        linhas = []
        for _, linha in dados.sort_values("eventos", ascending=False).iterrows():
            cor = SITUACAO[linha["situacao"]]
            documento = linha["documento"] or "sem procedimento"
            linhas.append(
                f"""
                <div style="display:flex;align-items:center;gap:9px;
                            padding:7px 0;border-bottom:1px solid {estilo.BORDA}">
                  <span style="width:9px;height:9px;border-radius:50%;background:{cor};
                               flex-shrink:0"></span>
                  <span style="font-size:0.84rem;color:{estilo.TINTA}">
                    {linha['condicao']}
                  </span>
                  <span style="font-size:0.72rem;color:{estilo.TINTA_SUAVE};
                               margin-left:4px">{documento}</span>
                  <span style="margin-left:auto;font-size:0.84rem;font-weight:600;
                               color:{estilo.TINTA}">{_numero(linha['eventos'])}</span>
                </div>
                """
            )
        st.markdown("".join(linhas), unsafe_allow_html=True)


def _lacunas(defeitos: pd.DataFrame) -> None:
    pendentes = defeitos[~defeitos["documentada"]].sort_values("eventos", ascending=False)
    if pendentes.empty:
        return

    total = _numero(pendentes["eventos"].sum())
    with estilo.cartao("Defeitos sem procedimento", f"{total} eventos afetados"):
        for _, linha in pendentes.iterrows():
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:{estilo.ESPACO['md']}px;
                            padding:9px 0;border-bottom:1px solid {estilo.BORDA}">
                  <span style="width:7px;height:7px;border-radius:50%;
                               background:{estilo.ALERTA};flex-shrink:0"></span>
                  <span style="font-weight:600;color:{estilo.TINTA};font-size:0.88rem">
                    {linha['condicao']}
                  </span>
                  <span style="font-size:0.78rem;color:{estilo.TINTA_SECUNDARIA}">
                    {_numero(linha['eventos'])} eventos ·
                    {linha['frequencia_diaria']:.0f}/dia
                  </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<p style='font-size:0.8rem;color:{estilo.TINTA_SECUNDARIA};"
            f"margin-top:{estilo.ESPACO['md']}px'>O sistema não emite recomendação para "
            "esses defeitos. Cadastre o procedimento em <b>Documentos</b> para que passem "
            "a ser atendidos.</p>",
            unsafe_allow_html=True,
        )


def _serie_temporal(dados: dict) -> None:
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
    estilo.aplicar_layout(figura, altura=280)
    figura.update_layout(hovermode="x unified")
    st.plotly_chart(figura, use_container_width=True)
    st.markdown(
        f"<p style='font-size:0.78rem;color:{estilo.TINTA_SUAVE};line-height:1.5'>"
        "Cada campanha de ensaio concentra um modo de falha, em janelas quase disjuntas. "
        "É por isso que a data não entra como atributo do modelo: ela prediz o rótulo por "
        "construção.</p>",
        unsafe_allow_html=True,
    )


def _rotacao(dados: dict) -> None:
    """Barras neutras, com a rotação mais frequente destacada no acento."""
    rpm = pd.DataFrame(
        {
            "rpm": list(dados["eventos_por_rpm"].keys()),
            "eventos": list(dados["eventos_por_rpm"].values()),
        }
    )
    maximo = rpm["eventos"].max()
    cores = [estilo.ACENTO if v == maximo else "#E3E8EF" for v in rpm["eventos"]]

    figura = px.bar(rpm, x="rpm", y="eventos", labels={"rpm": "rpm", "eventos": ""})
    figura.update_traces(
        marker_color=cores,
        marker_line_width=2,
        marker_line_color=estilo.SUPERFICIE,
        hovertemplate="<b>%{x} rpm</b><br>%{y:,} eventos<extra></extra>",
    )
    estilo.aplicar_layout(figura, altura=280)
    st.plotly_chart(figura, use_container_width=True)
    st.markdown(
        f"<p style='font-size:0.78rem;color:{estilo.TINTA_SUAVE};line-height:1.5'>"
        "Cinco rotações distintas em todo o histórico: são campanhas de bancada, não "
        "operação contínua.</p>",
        unsafe_allow_html=True,
    )


def _tabela(condicoes: pd.DataFrame) -> None:
    with estilo.cartao(
        "Detalhamento por condição", "grafias = formas distintas de anotação do operador"
    ):
        busca = st.text_input(
            "Filtrar condição",
            placeholder="Filtrar por condição…",
            label_visibility="collapsed",
        )
        recorte = (
            condicoes[condicoes["condicao"].str.contains(busca, case=False)]
            if busca
            else condicoes
        )
        st.dataframe(
            recorte[
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
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "eventos": st.column_config.NumberColumn(format="%d"),
                "% do total": st.column_config.NumberColumn(format="%.2f%%"),
                "eventos/dia": st.column_config.NumberColumn(format="%.0f"),
            },
        )
        st.markdown(
            f"<p style='font-size:0.78rem;color:{estilo.TINTA_SUAVE};margin-top:6px'>"
            "A normalização canônica reduz as 151 anotações do histórico às 17 condições "
            "reais.</p>",
            unsafe_allow_html=True,
        )


def renderizar(cliente: ClienteApi) -> None:
    try:
        dados = cliente.estatisticas()
        sistema = cliente.sistema()
    except ApiIndisponivel:
        estilo.topo("Painel do histórico", "Panorama dos eventos monitorados.")
        aviso_api_indisponivel()
        return

    resumo = dados["resumo"]
    etiquetas = (
        estilo.chip(sistema["modelo"], estilo.SUCESSO, icone="ponto"),
        estilo.chip(
            f"{resumo['primeiro_evento'][:10]} — {resumo['ultimo_evento'][:10]}"
        ),
    )
    if estilo.topo(
        "Painel do histórico",
        "Panorama dos eventos monitorados e da cobertura documental por defeito.",
        etiquetas=etiquetas,
        acao="Analisar evento",
        icone_acao="vital_signs",
    ):
        st.session_state.pagina = "Análise de evento"
        st.rerun()

    condicoes = pd.DataFrame(dados["condicoes"])
    defeitos = condicoes[condicoes["tipo_condicao"] == "defeito"].copy()

    _indicadores(resumo)
    st.write("")

    with estilo.cartao(
        "Ocorrências por condição", f"{resumo['dias_com_registro']} dias com registro"
    ):
        _cobertura(defeitos)

    st.write("")
    _lacunas(defeitos)

    st.write("")
    esquerda, direita = st.columns([3, 2])
    with esquerda, estilo.cartao("Eventos ao longo do tempo"):
        _serie_temporal(dados)
    with direita, estilo.cartao("Rotação"):
        _rotacao(dados)

    st.write("")
    _tabela(condicoes)
