"""Componentes compartilhados pela API (ADR-002).

Os três componentes pesados — índice k-NN sobre 166.796 eventos, modelo de embeddings de
1,1 GB e cliente do modelo de linguagem — são construídos uma única vez e reaproveitados
entre requisições. Reconstruí-los por chamada tornaria a API inutilizável.

A inicialização é preguiçosa e protegida por cache: o primeiro acesso paga o custo, os
seguintes não. Isso mantém a importação do módulo barata, o que importa para os testes.

**A construção é serializada por uma trava**, e não apenas memoizada. O ``lru_cache`` não
é atômico: enquanto a primeira chamada ainda constrói, as seguintes não encontram nada em
cache e entram também. O FastAPI executa rotas síncronas em um *pool* de threads, então
requisições concorrentes durante a subida — um cliente que repete a chamada porque a
primeira ainda não voltou, que é o comportamento normal de quem espera — construíam cada
uma a sua própria cópia do modelo. Observado ao empacotar: com o limite de memória do
contêiner, o processo era encerrado e reiniciado em laço.

A trava é reentrante porque :func:`obter_roteador` depende de duas das outras fábricas.
"""

from __future__ import annotations

import threading
from functools import lru_cache

from src.rag.gerador import Gerador
from src.rag.indice_documental import IndiceDocumental
from src.rag.registro import RegistroDocumentos
from src.rag.roteador import Roteador
from src.similarity.indice import IndiceSimilaridade

#: Serializa a construção dos componentes pesados. Reentrante — ver o cabeçalho.
_construcao = threading.RLock()


@lru_cache(maxsize=1)
def _indice_similaridade() -> IndiceSimilaridade:
    return IndiceSimilaridade.a_partir_do_arquivo()


@lru_cache(maxsize=1)
def _indice_documental() -> IndiceDocumental:
    indice = IndiceDocumental()
    indice.garantir_indexado()
    return indice


@lru_cache(maxsize=1)
def _registro() -> RegistroDocumentos:
    return RegistroDocumentos()


@lru_cache(maxsize=1)
def _roteador() -> Roteador:
    return Roteador(_indice_documental(), registro=_registro())


@lru_cache(maxsize=1)
def _gerador() -> Gerador:
    return Gerador()


def obter_indice_similaridade() -> IndiceSimilaridade:
    with _construcao:
        return _indice_similaridade()


def obter_indice_documental() -> IndiceDocumental:
    with _construcao:
        return _indice_documental()


def obter_registro() -> RegistroDocumentos:
    with _construcao:
        return _registro()


def obter_roteador() -> Roteador:
    """Roteador ciente dos procedimentos cadastrados em operação (ADR-014).

    O registro é consultado a cada decisão, e não copiado na inicialização: um documento
    cadastrado passa a valer na consulta seguinte, sem reinício do serviço.
    """
    with _construcao:
        return _roteador()


def obter_gerador() -> Gerador:
    with _construcao:
        return _gerador()
