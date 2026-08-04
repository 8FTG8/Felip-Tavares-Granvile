"""Testes das agregações do painel (ADR-002).

Rodam sobre a amostra versionada, com o índice de similaridade real — as agregações são
cálculo sobre dados, e substituí-los por dublês testaria apenas a serialização.
"""

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencias import obter_indice_similaridade, obter_registro
from src.api.estatisticas import resumir, validar_taxonomia
from src.ingestion.eventos import carregar_eventos
from src.rag.registro import RegistroDocumentos
from src.similarity.indice import IndiceSimilaridade

AMOSTRA = Path(__file__).resolve().parents[1] / "data" / "amostra_banner.csv"


@pytest.fixture(scope="module")
def eventos() -> pd.DataFrame:
    if not AMOSTRA.exists():
        pytest.skip("amostra ausente: rode scripts/gerar_amostra.py")
    return carregar_eventos(AMOSTRA)


@pytest.fixture(scope="module")
def indice(eventos: pd.DataFrame) -> IndiceSimilaridade:
    return IndiceSimilaridade(eventos, vizinhos=5)


@pytest.fixture
def cliente(indice: IndiceSimilaridade, tmp_path: Path) -> TestClient:
    app.dependency_overrides[obter_indice_similaridade] = lambda: indice
    app.dependency_overrides[obter_registro] = lambda: RegistroDocumentos(tmp_path / "r.db")
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestAgregacao:
    def test_totais_fecham(self, eventos: pd.DataFrame) -> None:
        panorama = resumir(eventos)
        assert (
            panorama.resumo.total_defeitos + panorama.resumo.total_estados
            <= panorama.resumo.total_eventos
        )
        assert sum(c.eventos for c in panorama.condicoes) == panorama.resumo.total_eventos

    def test_doze_familias_de_defeito(self, eventos: pd.DataFrame) -> None:
        assert resumir(eventos).resumo.familias_de_defeito == 12

    def test_condicoes_ordenadas_por_volume(self, eventos: pd.DataFrame) -> None:
        contagens = [c.eventos for c in resumir(eventos).condicoes]
        assert contagens == sorted(contagens, reverse=True)

    def test_taxonomia_respeitada(self, eventos: pd.DataFrame) -> None:
        validar_taxonomia(resumir(eventos))

    def test_janela_temporal_coerente(self, eventos: pd.DataFrame) -> None:
        resumo = resumir(eventos).resumo
        assert resumo.primeiro_evento < resumo.ultimo_evento
        assert resumo.dias_com_registro > 0

    def test_grafias_distintas_por_condicao(self, eventos: pd.DataFrame) -> None:
        """Evidência da normalização canônica: o operador escreveu a mesma condição de
        muitas formas, e o painel mostra quantas."""
        por_condicao = {c.condicao: c for c in resumir(eventos).condicoes}
        assert por_condicao["desbalanceado"].rotulos_brutos > 5

    def test_frequencia_por_dia_com_registro(self, eventos: pd.DataFrame) -> None:
        for condicao in resumir(eventos).condicoes:
            assert condicao.frequencia_diaria > 0
            assert condicao.dias_com_registro >= 1


class TestEndpoint:
    def test_responde(self, cliente: TestClient) -> None:
        assert cliente.get("/estatisticas").status_code == 200

    def test_resumo_completo(self, cliente: TestClient) -> None:
        resumo = cliente.get("/estatisticas").json()["resumo"]
        assert resumo["total_eventos"] > 0
        assert resumo["familias_de_defeito"] == 12
        assert 0.0 <= resumo["cobertura_documental"] <= 1.0

    def test_cobertura_medida_em_eventos(self, cliente: TestClient) -> None:
        """Dizer que 9 das 12 famílias têm procedimento esconde que essas 9 respondem por
        80% das ocorrências. O painel informa o alcance real."""
        corpo = cliente.get("/estatisticas").json()
        documentados = sum(
            c["eventos"]
            for c in corpo["condicoes"]
            if c["tipo_condicao"] == "defeito" and c["documentada"]
        )
        esperado = documentados / corpo["resumo"]["total_defeitos"]
        assert corpo["resumo"]["cobertura_documental"] == pytest.approx(esperado, abs=1e-4)

    def test_situacao_documental_por_condicao(self, cliente: TestClient) -> None:
        condicoes = {c["condicao"]: c for c in cliente.get("/estatisticas").json()["condicoes"]}
        assert condicoes["rolamento_inner"]["documento"] == "Doc1"
        assert condicoes["cocked_rotor"]["documento"] == "Doc6"
        for sem_documento in ("falta_fase", "ventoinha", "eccentric_rotor"):
            assert not condicoes[sem_documento]["documentada"]

    def test_estados_nao_recebem_documento(self, cliente: TestClient) -> None:
        """Estado não é defeito e não entra na conta de cobertura (ADR-006)."""
        condicoes = {c["condicao"]: c for c in cliente.get("/estatisticas").json()["condicoes"]}
        assert condicoes["normal"]["documento"] is None
        assert not condicoes["normal"]["documentada"]

    def test_series_serializaveis(self, cliente: TestClient) -> None:
        corpo = cliente.get("/estatisticas").json()
        assert corpo["eventos_por_dia"]
        assert all(len(dia) == 10 for dia in corpo["eventos_por_dia"])
        assert corpo["eventos_por_rpm"]

    def test_rpm_e_quase_categorico(self, cliente: TestClient) -> None:
        """Cinco rotações distintas em todo o histórico — é bancada de ensaio, não
        operação contínua."""
        assert len(cliente.get("/estatisticas").json()["eventos_por_rpm"]) <= 6

    def test_cadastro_altera_a_cobertura(self, cliente: TestClient, tmp_path: Path) -> None:
        registro = RegistroDocumentos(tmp_path / "r.db")
        registro.registrar("ventoinha", "DocOp-ventoinha", "x.pdf", 10, "nativo")
        app.dependency_overrides[obter_registro] = lambda: registro

        condicoes = {c["condicao"]: c for c in cliente.get("/estatisticas").json()["condicoes"]}
        assert condicoes["ventoinha"]["documentada"]
        assert condicoes["ventoinha"]["documento"] == "DocOp-ventoinha"
