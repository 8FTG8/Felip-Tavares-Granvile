"""API de manutenção prescritiva (ADR-002).

Em ambiente industrial o consumidor natural do sistema não é uma pessoa em um navegador:
é o supervisório, o CMMS ou o broker que recebe os eventos dos sensores. A API é o
contrato que torna essa integração possível; a interface gráfica é apenas um dos clientes.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from src.api.esquemas import (
    AnaliseEvento,
    ContextoHistorico,
    CoberturaDocumental,
    CondicaoNoHistorico,
    Consulta,
    DocumentoRegistrado,
    EventoSensor,
    Fonte,
    OcorrenciaSimilar,
    PainelHistorico,
    PerguntaOpcional,
    RespostaChat,
    ResumoCondicao,
    ResumoHistorico,
)
from src.api.dependencias import (
    obter_gerador,
    obter_indice_documental,
    obter_indice_similaridade,
    obter_registro,
    obter_roteador,
)
from src.api.estatisticas import resumir
from src.ingestion.rotulos import DEFEITOS
from src.rag.cadastro import CadastroInvalido, cadastrar
from src.rag.gerador import Gerador
from src.rag.indice_documental import IndiceDocumental
from src.rag.mapeamento import cobertura
from src.rag.registro import RegistroDocumentos
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


@app.get(
    "/estatisticas",
    response_model=PainelHistorico,
    summary="Agregações do histórico para o painel",
    tags=["Estatísticas"],
)
def consultar_estatisticas(
    similaridade: IndiceSimilaridade = Depends(obter_indice_similaridade),
    registro: RegistroDocumentos = Depends(obter_registro),
) -> PainelHistorico:
    """Panorama do histórico monitorado, com a situação documental de cada condição.

    A cobertura documental é calculada em eventos, não em famílias: dizer que 9 das 12
    famílias têm procedimento esconde que essas 9 respondem por 80% das ocorrências. É a
    proporção de eventos que mede o alcance real da base documental.
    """
    panorama = resumir(similaridade.eventos)
    cadastrados = {d.condicao for d in registro.listar()}

    def documento_de(condicao: str) -> str | None:
        estatico = cobertura(condicao).documento
        if estatico:
            return estatico
        return next(
            (d.documento for d in registro.listar() if d.condicao == condicao), None
        )

    condicoes = [
        CondicaoNoHistorico(
            condicao=c.condicao,
            tipo_condicao=c.tipo_condicao,
            eventos=c.eventos,
            proporcao=round(c.proporcao, 4),
            primeira=c.primeira,
            ultima=c.ultima,
            dias_com_registro=c.dias_com_registro,
            frequencia_diaria=round(c.frequencia_diaria, 2),
            rotulos_brutos=c.rotulos_brutos,
            documentada=(
                c.condicao in DEFEITOS
                and (cobertura(c.condicao).documentada or c.condicao in cadastrados)
            ),
            documento=documento_de(c.condicao) if c.condicao in DEFEITOS else None,
        )
        for c in panorama.condicoes
    ]

    defeitos_documentados = sum(
        c.eventos for c in condicoes if c.tipo_condicao == "defeito" and c.documentada
    )

    return PainelHistorico(
        resumo=ResumoHistorico(
            total_eventos=panorama.resumo.total_eventos,
            total_defeitos=panorama.resumo.total_defeitos,
            total_estados=panorama.resumo.total_estados,
            familias_de_defeito=panorama.resumo.familias_de_defeito,
            primeiro_evento=panorama.resumo.primeiro_evento,
            ultimo_evento=panorama.resumo.ultimo_evento,
            dias_com_registro=panorama.resumo.dias_com_registro,
            cobertura_documental=round(
                defeitos_documentados / panorama.resumo.total_defeitos, 4
            )
            if panorama.resumo.total_defeitos
            else 0.0,
        ),
        condicoes=condicoes,
        eventos_por_dia={
            dia.strftime("%Y-%m-%d"): int(total)
            for dia, total in panorama.eventos_por_dia.items()
        },
        eventos_por_rpm={
            f"{int(rpm)}": total for rpm, total in panorama.eventos_por_rpm.items()
        },
    )


#: Resposta quando a pergunta chega sem condição associada. O sistema não tenta adivinhar
#: a que equipamento o técnico se refere: com seis procedimentos que compartilham seções
#: de mesmo nome, escolher um por conta própria seria sortear a fonte da resposta.
SEM_CONDICAO = (
    "**Preciso saber a que condição do equipamento você se refere.**\n\n"
    "As orientações vêm dos procedimentos técnicos da empresa, e cada procedimento cobre "
    "um tipo de falha específico. Sem saber a condição, eu teria de escolher um documento "
    "por conta própria — e a resposta poderia vir do procedimento errado.\n\n"
    "Informe a condição do evento (por exemplo, `cocked_rotor`, `desalinhado`, "
    "`rolamento_inner`) ou selecione um evento registrado."
)


@app.post(
    "/chat",
    response_model=RespostaChat,
    summary="Responde uma pergunta técnica sobre a condição de um equipamento",
    tags=["Chat"],
)
def conversar(
    consulta: Consulta,
    roteador: Roteador = Depends(obter_roteador),
    gerador: Gerador = Depends(obter_gerador),
) -> RespostaChat:
    """Consulta livre, submetida às mesmas barreiras da análise de evento.

    O chat não é uma porta lateral para o modelo: a pergunta é roteada pela condição
    informada, e a resposta só é gerada se houver procedimento com trecho relevante. Sem
    condição, o sistema pede a definição em vez de escolher um documento por conta
    própria.
    """
    if not consulta.condicao:
        return RespostaChat(
            resposta=SEM_CONDICAO,
            caminho="sem_condicao",
            gerada_por_llm=False,
        )

    decisao = roteador.decidir(consulta.condicao, consulta.pergunta)
    recomendacao = gerador.responder(
        decisao,
        consulta.pergunta,
        historico=[turno.model_dump() for turno in consulta.historico],
    )

    return RespostaChat(
        resposta=recomendacao.texto,
        caminho=decisao.caminho.value,
        condicao=decisao.condicao,
        documento=decisao.documento,
        motivo_recusa=decisao.motivo.value if decisao.motivo else None,
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
    )


@app.post(
    "/chat/fluxo",
    summary="Mesma consulta, com a resposta transmitida em tempo real",
    tags=["Chat"],
    response_class=StreamingResponse,
)
def conversar_em_fluxo(
    consulta: Consulta,
    roteador: Roteador = Depends(obter_roteador),
    gerador: Gerador = Depends(obter_gerador),
) -> StreamingResponse:
    """Versão incremental de :func:`conversar`, para a interface de chat.

    Em estação sem GPU dedicada a geração leva dezenas de segundos, e ver o texto surgindo
    torna a espera aceitável. As recusas continuam instantâneas — são compostas em código.
    """
    if not consulta.condicao:
        return StreamingResponse(iter([SEM_CONDICAO]), media_type="text/plain; charset=utf-8")

    decisao = roteador.decidir(consulta.condicao, consulta.pergunta)
    fluxo = gerador.responder_em_fluxo(
        decisao,
        consulta.pergunta,
        historico=[turno.model_dump() for turno in consulta.historico],
    )
    return StreamingResponse(
        fluxo,
        media_type="text/plain; charset=utf-8",
        headers={
            "X-Caminho": decisao.caminho.value,
            "X-Condicao": decisao.condicao,
            "X-Documento": decisao.documento or "",
        },
    )


@app.post(
    "/documentos",
    response_model=DocumentoRegistrado,
    status_code=201,
    summary="Cadastra um procedimento técnico para uma condição sem documentação",
    tags=["Documentos"],
)
async def cadastrar_documento(
    condicao: Annotated[str, Form(description="Condição que o procedimento cobre")],
    arquivo: Annotated[UploadFile, File(description="PDF do procedimento técnico")],
    indice: IndiceDocumental = Depends(obter_indice_documental),
    registro: RegistroDocumentos = Depends(obter_registro),
) -> DocumentoRegistrado:
    """Cadastra o procedimento que faltava e passa a atender a condição.

    Este endpoint é o que torna verdadeira a instrução dada nas recusas. O documento
    recebe o mesmo tratamento da base original — extração adaptativa, fatiamento por
    seção e indexação — e a condição é atendida já na consulta seguinte, sem reinício.
    """
    if not arquivo.filename or not arquivo.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Envie o procedimento em formato PDF.")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporario:
        temporario.write(await arquivo.read())
        caminho = Path(temporario.name)

    try:
        resultado = cadastrar(condicao, caminho, indice, registro)
    except CadastroInvalido as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
    finally:
        caminho.unlink(missing_ok=True)

    return DocumentoRegistrado(
        condicao=resultado.documento.condicao,
        documento=resultado.documento.documento,
        trechos=resultado.documento.trechos,
        origem=resultado.documento.origem,
        cadastrado_em=resultado.documento.cadastrado_em,
        secoes=resultado.secoes,
    )


@app.get(
    "/documentos/cobertura",
    response_model=list[CoberturaDocumental],
    summary="Situação documental de cada família de defeito",
    tags=["Documentos"],
)
def consultar_cobertura(
    registro: RegistroDocumentos = Depends(obter_registro),
) -> list[CoberturaDocumental]:
    """Lista quais defeitos têm procedimento e quais aguardam cadastro.

    É a visão que orienta a equipe sobre onde a base documental está incompleta — e a
    origem dos números exibidos no painel de cobertura.
    """
    cadastrados = {d.condicao: d for d in registro.listar()}
    situacoes: list[CoberturaDocumental] = []

    for condicao in sorted(DEFEITOS):
        estatica = cobertura(condicao)
        cadastrado = cadastrados.get(condicao)
        situacoes.append(
            CoberturaDocumental(
                condicao=condicao,
                documentada=estatica.documentada or cadastrado is not None,
                documento=estatica.documento or (cadastrado.documento if cadastrado else None),
                cadastrado_em_operacao=not estatica.documentada and cadastrado is not None,
                justificativa="" if cadastrado else estatica.justificativa,
            )
        )
    return situacoes
