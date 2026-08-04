"""API de manutenção prescritiva (ADR-002).

Em ambiente industrial o consumidor natural do sistema não é uma pessoa em um navegador:
é o supervisório, o CMMS ou o broker que recebe os eventos dos sensores. A API é o
contrato que torna essa integração possível; a interface gráfica é apenas um dos clientes.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI

from src.api.esquemas import (
    AnaliseEvento,
    ContextoHistorico,
    EventoSensor,
    Fonte,
    OcorrenciaSimilar,
    PerguntaOpcional,
    ResumoCondicao,
)
from src.api.dependencias import (
    obter_gerador,
    obter_indice_similaridade,
    obter_roteador,
)
from src.rag.gerador import Gerador
from src.rag.roteador import Roteador
from src.similarity.indice import ContextoSimilaridade, IndiceSimilaridade

app = FastAPI(
    title="Manutenção Prescritiva — SENAI SC",
    description=(
        "Recebe eventos de sensores de vibração, localiza ocorrências históricas "
        "semelhantes e prescreve a ação corretiva com base na documentação técnica da "
        "empresa. Quando não há procedimento cadastrado para o defeito identificado, o "
        "sistema recusa-se a recomendar e solicita o cadastro do documento."
    ),
    version="0.1.0",
)


def _montar_contexto(contexto: ContextoSimilaridade) -> ContextoHistorico:
    return ContextoHistorico(
        total_ocorrencias_similares=contexto.total_ocorrencias_similares,
        ocorrencias_por_condicao=[
            ResumoCondicao(
                condicao=o.condicao,
                tipo_condicao=o.tipo_condicao,
                vizinhos=o.vizinhos,
                ocorrencias_historicas=o.ocorrencias_historicas,
                primeira=o.primeira,
                ultima=o.ultima,
                dias_com_registro=o.dias_com_registro,
                frequencia_diaria=round(o.frequencia_diaria, 2),
            )
            for o in contexto.ocorrencias
        ],
        vizinhos=[
            OcorrenciaSimilar(
                id=v.id,
                created_at=v.created_at,
                condicao=v.condicao,
                tipo_condicao=v.tipo_condicao,
                rotulo_bruto=v.rotulo_bruto,
                rpm=v.rpm,
                similaridade=round(v.similaridade, 4),
                leituras_identicas=v.leituras_identicas,
            )
            for v in contexto.vizinhos
        ],
        distribuicao_temporal={
            dia.strftime("%Y-%m-%d"): int(total)
            for dia, total in contexto.distribuicao_temporal.items()
        },
        contexto_operacional={
            chave: round(valor, 4) for chave, valor in contexto.contexto_operacional.items()
        },
    )


@app.post(
    "/eventos/analisar",
    response_model=AnaliseEvento,
    summary="Analisa um evento de sensor e prescreve a ação corretiva",
    tags=["Eventos"],
)
def analisar_evento(
    evento: EventoSensor,
    consulta: PerguntaOpcional = Depends(),
    similaridade: IndiceSimilaridade = Depends(obter_indice_similaridade),
    roteador: Roteador = Depends(obter_roteador),
    gerador: Gerador = Depends(obter_gerador),
) -> AnaliseEvento:
    """Executa o pipeline completo para um evento.

    A decisão sobre responder ou recusar é tomada antes de qualquer geração de texto, e o
    modelo de linguagem só é acionado quando há respaldo documental. O contexto histórico
    é devolvido nos três caminhos: mesmo sem prescrição a recomendar, saber quantas vezes
    aquele padrão já ocorreu e com que frequência é informação útil à manutenção.
    """
    contexto = similaridade.consultar(evento.para_consulta())
    decisao = roteador.decidir(evento.fault, consulta.pergunta)
    recomendacao = gerador.responder(decisao, consulta.pergunta)

    return AnaliseEvento(
        condicao=decisao.condicao,
        tipo_condicao=decisao.tipo_condicao,
        rotulo_bruto=decisao.rotulo_bruto,
        caminho=decisao.caminho.value,
        motivo_recusa=decisao.motivo.value if decisao.motivo else None,
        documento=decisao.documento,
        recomendacao=recomendacao.texto,
        gerada_por_llm=recomendacao.gerada_por_llm,
        modelo=recomendacao.modelo,
        fontes=[
            Fonte(
                documento=t.trecho.documento,
                numero_secao=t.trecho.numero_secao,
                titulo_secao=t.trecho.titulo_secao,
                citacao=t.citacao,
                relevancia=round(t.relevancia, 4),
                origem=t.trecho.origem,
            )
            for t in decisao.trechos
        ],
        contexto=_montar_contexto(contexto),
    )
