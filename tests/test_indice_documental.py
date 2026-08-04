"""Testes da recuperação semântica (ADR-009).

A indexação carrega o modelo de embeddings (~1,1 GB) e leva cerca de um minuto. Por isso
o índice é construído uma única vez por sessão de testes, em diretório temporário, sem
tocar a persistência de trabalho.
"""

from pathlib import Path

import pytest

from src.rag.documentos import DIRETORIO_DOCUMENTOS, carregar_base_documental
from src.rag.indice_documental import (
    PREFIXO_CONSULTA,
    PREFIXO_DOCUMENTO,
    IndiceDocumental,
)
from src.rag.mapeamento import cobertura

pytestmark = pytest.mark.lento


@pytest.fixture(scope="session")
def indice(tmp_path_factory: pytest.TempPathFactory) -> IndiceDocumental:
    if not any(DIRETORIO_DOCUMENTOS.glob("Doc*.pdf")):
        pytest.skip("base documental ausente")
    destino: Path = tmp_path_factory.mktemp("chroma")
    indice = IndiceDocumental(persistencia=destino, colecao="teste")
    indice.indexar(recriar=False)
    return indice


class TestIndexacao:
    def test_indexa_a_base_completa(self, indice: IndiceDocumental) -> None:
        assert indice.total_trechos == len(carregar_base_documental())

    def test_prefixos_do_e5_declarados(self) -> None:
        """O e5 foi treinado com marcadores assimétricos; omiti-los degrada a
        recuperação silenciosamente, sem erro algum."""
        assert PREFIXO_DOCUMENTO.startswith("passage")
        assert PREFIXO_CONSULTA.startswith("query")

    def test_reindexar_nao_duplica(self, indice: IndiceDocumental) -> None:
        antes = indice.total_trechos
        indice.indexar()
        assert indice.total_trechos == antes


class TestRecuperacao:
    def test_encontra_trecho_pertinente(self, indice: IndiceDocumental) -> None:
        recuperados = indice.buscar("como corrigir o desalinhamento", documento="Doc2")
        assert recuperados
        assert all(r.trecho.documento == "Doc2" for r in recuperados)
        assert 0.0 <= recuperados[0].relevancia <= 1.0

    def test_ordenado_por_relevancia(self, indice: IndiceDocumental) -> None:
        recuperados = indice.buscar("balanceamento do rotor", documento="Doc3")
        relevancias = [r.relevancia for r in recuperados]
        assert relevancias == sorted(relevancias, reverse=True)

    def test_respeita_o_numero_de_trechos(self, indice: IndiceDocumental) -> None:
        assert len(indice.buscar("vibração", documento="Doc1", trechos=2)) == 2

    def test_recupera_do_documento_com_ocr(self, indice: IndiceDocumental) -> None:
        """O Doc1 passou por OCR; o ruído não pode inviabilizar a recuperação dos 40%
        de defeitos que ele cobre."""
        recuperados = indice.buscar(
            "como corrigir defeito na pista interna do rolamento", documento="Doc1"
        )
        assert recuperados
        assert recuperados[0].relevancia > 0.5


class TestFiltroPorDocumento:
    """O filtro elimina por construção a alucinação mais provável do projeto: recuperar
    a seção certa do documento errado, já que os seis procedimentos têm seções
    homônimas."""

    def test_filtro_restringe_de_fato(self, indice: IndiceDocumental) -> None:
        for documento in ("Doc1", "Doc4", "Doc6"):
            recuperados = indice.buscar("segurança do procedimento", documento=documento)
            assert {r.trecho.documento for r in recuperados} == {documento}

    def test_busca_global_cruza_documentos(self, indice: IndiceDocumental) -> None:
        """Sem filtro, uma pergunta genérica alcança vários procedimentos — a razão de
        o filtro existir."""
        recuperados = indice.buscar("registro da intervenção", trechos=6)
        assert len({r.trecho.documento for r in recuperados}) > 1

    def test_roteamento_completo_do_defeito_ao_trecho(self, indice: IndiceDocumental) -> None:
        """Caminho de produção: condição canônica → documento → trecho citável."""
        alvo = cobertura("cocked_rotor")
        recuperados = indice.buscar("como corrigir o rotor inclinado", documento=alvo.documento)
        assert recuperados
        assert recuperados[0].trecho.documento == "Doc6"
        assert "Doc6" in recuperados[0].citacao


class TestIndiceVazio:
    def test_busca_em_indice_vazio_nao_quebra(self, tmp_path: Path) -> None:
        vazio = IndiceDocumental(persistencia=tmp_path, colecao="vazio")
        assert vazio.buscar("qualquer pergunta") == []
