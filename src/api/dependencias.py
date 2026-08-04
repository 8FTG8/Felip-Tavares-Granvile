"""Componentes compartilhados pela API (ADR-002).

Os três componentes pesados — índice k-NN sobre 166.796 eventos, modelo de embeddings de
1,1 GB e cliente do modelo de linguagem — são construídos uma única vez e reaproveitados
entre requisições. Reconstruí-los por chamada tornaria a API inutilizável.

A inicialização é preguiçosa e protegida por cache: o primeiro acesso paga o custo, os
seguintes não. Isso mantém a importação do módulo barata, o que importa para os testes.
"""

from __future__ import annotations

from functools import lru_cache

from src.rag.gerador import Gerador
from src.rag.indice_documental import IndiceDocumental
from src.rag.registro import RegistroDocumentos
from src.rag.roteador import Roteador
from src.similarity.indice import IndiceSimilaridade


@lru_cache(maxsize=1)
def obter_indice_similaridade() -> IndiceSimilaridade:
    return IndiceSimilaridade.a_partir_do_arquivo()


@lru_cache(maxsize=1)
def obter_indice_documental() -> IndiceDocumental:
    indice = IndiceDocumental()
    indice.garantir_indexado()
    return indice


@lru_cache(maxsize=1)
def obter_registro() -> RegistroDocumentos:
    return RegistroDocumentos()


@lru_cache(maxsize=1)
def obter_roteador() -> Roteador:
    """Roteador ciente dos procedimentos cadastrados em operação (ADR-014).

    O registro é consultado a cada decisão, e não copiado na inicialização: um documento
    cadastrado passa a valer na consulta seguinte, sem reinício do serviço.
    """
    return Roteador(obter_indice_documental(), registro=obter_registro())


@lru_cache(maxsize=1)
def obter_gerador() -> Gerador:
    return Gerador()
