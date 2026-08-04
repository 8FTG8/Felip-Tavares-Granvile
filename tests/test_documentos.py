"""Testes da extração e do fatiamento documental (ADR-009, ADR-012).

Os testes rodam sobre os PDFs originais e sobre o cache de extração. O Doc1 exige OCR e
seu processamento leva cerca de 80 segundos na primeira execução; a partir daí, o cache
em ``data/processed`` responde de imediato.
"""

from pathlib import Path

import pytest

from src.rag.documentos import (
    DIRETORIO_DOCUMENTOS,
    Trecho,
    _e_titulo_plausivel,
    _secoes,
    carregar_base_documental,
    carregar_documento,
    fatiar,
)

#: Número de seções por documento, conferido manualmente contra os PDFs.
SECOES_ESPERADAS = {"Doc1": 25, "Doc2": 16, "Doc3": 16, "Doc4": 19, "Doc5": 18, "Doc6": 21}


def _pular_se_ausente(documento: str) -> Path:
    caminho = DIRETORIO_DOCUMENTOS / f"{documento}.pdf"
    if not caminho.exists():
        pytest.skip(f"{documento}.pdf ausente: consulte o README para o download")
    return caminho


@pytest.fixture(scope="module")
def base() -> tuple[Trecho, ...]:
    if not any(DIRETORIO_DOCUMENTOS.glob("Doc*.pdf")):
        pytest.skip("base documental ausente")
    return carregar_base_documental()


class TestDeteccaoDeSecoes:
    def test_ignora_lista_de_passos(self) -> None:
        """Passos de procedimento têm a forma de cabeçalho e não podem virar seção."""
        texto = "\n".join(
            [
                "1. Objetivo",
                "Descreve o procedimento.",
                "2. Segurança",
                "1. Desligar o equipamento.",
                "2. Aplicar bloqueio e etiquetagem.",
                "3. Confirmar ausência de energia.",
                "3. Diagnóstico",
                "Medir a vibração.",
            ]
        )
        assert [numero for numero, _, _ in _secoes(texto)] == [1, 2, 3]

    def test_escolhe_a_cadeia_mais_longa_e_nao_a_primeira(self) -> None:
        """Se o primeiro cabeçalho se perder na extração, a detecção não pode
        descarrilar para dentro de uma enumeração interna — o caso real do Doc1, cujo
        '1. Objetivo' foi lido pelo OCR como '1. 0bjetivo'."""
        texto = "\n".join(
            [
                "1. 0bjetivo",
                "Texto da primeira seção.",
                "2. Introdução",
                "1. Passo um.",
                "2. Passo dois.",
                "3. Diagnóstico",
                "4. Correção",
                "5. Validação",
            ]
        )
        assert [numero for numero, _, _ in _secoes(texto)] == [1, 2, 3, 4, 5]

    def test_titulo_plausivel(self) -> None:
        assert _e_titulo_plausivel("Correção da Falha")
        assert _e_titulo_plausivel("0bjetivo")  # ruído de OCR
        assert not _e_titulo_plausivel("Desligar o equipamento.")
        assert not _e_titulo_plausivel("500")

    def test_documento_sem_secoes_vira_trecho_unico(self) -> None:
        trechos = fatiar("Texto corrido sem estrutura.", documento="X", origem="nativo")
        assert len(trechos) == 1
        assert trechos[0].numero_secao == 0


class TestExtracao:
    @pytest.mark.parametrize("documento", sorted(SECOES_ESPERADAS))
    def test_numero_de_secoes(self, documento: str) -> None:
        caminho = _pular_se_ausente(documento)
        trechos = carregar_documento(caminho)
        assert len(trechos) == SECOES_ESPERADAS[documento]

    def test_doc1_exige_ocr(self) -> None:
        """17 páginas de imagem, sem camada de texto (ADR-012)."""
        trechos = carregar_documento(_pular_se_ausente("Doc1"))
        assert all(t.origem == "ocr" for t in trechos)

    def test_demais_documentos_sao_nativos(self) -> None:
        for documento in ("Doc2", "Doc3", "Doc4", "Doc5", "Doc6"):
            trechos = carregar_documento(_pular_se_ausente(documento))
            assert all(t.origem == "nativo" for t in trechos), documento

    def test_ocr_recupera_a_secao_prescritiva(self) -> None:
        """A seção 19 do Doc1 traz a correção da falha de rolamento — é o conteúdo que
        sustenta a recomendação para 40% dos defeitos do histórico."""
        trechos = {t.numero_secao: t for t in carregar_documento(_pular_se_ausente("Doc1"))}
        assert "orrec" in trechos[19].titulo_secao  # tolera perda de acento no OCR
        assert len(trechos[19].texto) > 200

    def test_titulo_do_documento_e_reconstruido(self) -> None:
        """O título ocupa mais de uma linha no PDF e compõe o texto indexado."""
        trechos = carregar_documento(_pular_se_ausente("Doc6"))
        assert "Rotor Inclinado" in trechos[0].titulo_documento

    def test_acentuacao_preservada_no_texto_nativo(self) -> None:
        trechos = carregar_documento(_pular_se_ausente("Doc2"))
        assert "Correção" in trechos[0].titulo_documento


class TestBaseDocumental:
    def test_carrega_os_seis_procedimentos(self, base: tuple[Trecho, ...]) -> None:
        assert {t.documento for t in base} == set(SECOES_ESPERADAS)
        assert len(base) == sum(SECOES_ESPERADAS.values())

    def test_todo_trecho_tem_conteudo(self, base: tuple[Trecho, ...]) -> None:
        assert all(t.texto.strip() for t in base)

    def test_identificador_unico(self, base: tuple[Trecho, ...]) -> None:
        identificadores = [t.identificador for t in base]
        assert len(set(identificadores)) == len(identificadores)

    def test_citacao_localiza_a_fonte(self, base: tuple[Trecho, ...]) -> None:
        """Rastreabilidade exigida pelo ADR-004: a resposta aponta documento e seção."""
        trecho = base[0]
        assert trecho.documento in trecho.citacao
        assert str(trecho.numero_secao) in trecho.citacao

    def test_conteudo_indexavel_carrega_o_cabecalho(self, base: tuple[Trecho, ...]) -> None:
        """Os seis procedimentos têm seções homônimas — Segurança, Registro da
        Intervenção —, e o cabeçalho é o que as distingue no espaço vetorial."""
        trecho = base[0]
        assert trecho.titulo_documento in trecho.conteudo_indexavel
        assert trecho.titulo_secao in trecho.conteudo_indexavel

    def test_secoes_homonimas_existem_de_fato(self, base: tuple[Trecho, ...]) -> None:
        titulos = [t.titulo_secao.lower() for t in base]
        repetidos = {t for t in titulos if titulos.count(t) > 1}
        assert repetidos, "sem seções homônimas o filtro por documento seria dispensável"
