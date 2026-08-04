"""Testes do endpoint de análise de evento (ADR-002).

Os componentes pesados são substituídos por dublês: a API é uma camada de composição, e
o que se verifica aqui é o contrato HTTP e a fidelidade da tradução entre o domínio e o
JSON — não o comportamento do k-NN ou do LLM, já coberto nos testes de cada módulo.
"""

from datetime import datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencias import (
    obter_gerador,
    obter_indice_similaridade,
    obter_roteador,
)
from src.rag.gerador import Gerador
from src.rag.roteador import Roteador
from src.similarity.indice import (
    ContextoSimilaridade,
    OcorrenciasPorCondicao,
    Vizinho,
)
from tests.test_gerador import ClienteFalso
from tests.test_indice import EVENTO_DO_ENUNCIADO
from tests.test_roteador import IndiceFalso

MOMENTO = pd.Timestamp("2026-06-01 21:32:53", tz="UTC")


class SimilaridadeFalsa:
    """Devolve um contexto fixo, com a forma exata do índice real."""

    def consultar(self, evento: dict, vizinhos: int | None = None, excluir_proprio: bool = True):
        return ContextoSimilaridade(
            condicao_informada="cocked_rotor",
            tipo_condicao_informada="defeito",
            rotulo_bruto=str(evento.get("fault")),
            vizinhos=[
                Vizinho(
                    id=114386,
                    created_at=MOMENTO,
                    condicao="cocked_rotor",
                    tipo_condicao="defeito",
                    rotulo_bruto="cocked_rotor_2",
                    rpm=1000.0,
                    distancia=0.0267,
                    similaridade=0.9740,
                    leituras_identicas=1,
                )
            ],
            ocorrencias=[
                OcorrenciasPorCondicao(
                    condicao="cocked_rotor",
                    tipo_condicao="defeito",
                    vizinhos=1,
                    ocorrencias_historicas=14275,
                    primeira=MOMENTO,
                    ultima=MOMENTO,
                    dias_com_registro=7,
                    frequencia_diaria=2039.2857,
                )
            ],
            distribuicao_temporal=pd.Series({MOMENTO.normalize(): 42}),
            contexto_operacional={"rpm_predominante": 1000.0, "similaridade_media": 0.842},
        )


@pytest.fixture
def cliente_llm() -> ClienteFalso:
    return ClienteFalso()


@pytest.fixture
def cliente(cliente_llm: ClienteFalso) -> TestClient:
    app.dependency_overrides[obter_indice_similaridade] = lambda: SimilaridadeFalsa()
    app.dependency_overrides[obter_roteador] = lambda: Roteador(IndiceFalso())
    app.dependency_overrides[obter_gerador] = lambda: Gerador(cliente=cliente_llm)
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestContratoDeEntrada:
    def test_aceita_o_json_do_enunciado(self, cliente: TestClient) -> None:
        """Inclui as colunas redundantes que a solução ignora: quem produz o evento é o
        banco corporativo, e o formato é dele."""
        assert cliente.post("/eventos/analisar", json=EVENTO_DO_ENUNCIADO).status_code == 200

    def test_rejeita_evento_sem_atributo_obrigatorio(self, cliente: TestClient) -> None:
        incompleto = {k: v for k, v in EVENTO_DO_ENUNCIADO.items() if k != "temperature_c"}
        resposta = cliente.post("/eventos/analisar", json=incompleto)
        assert resposta.status_code == 422
        assert "temperature_c" in resposta.text

    def test_rejeita_atributo_nao_numerico(self, cliente: TestClient) -> None:
        invalido = EVENTO_DO_ENUNCIADO | {"rpm": "mil"}
        assert cliente.post("/eventos/analisar", json=invalido).status_code == 422

    def test_evento_sem_rotulo_e_aceito(self, cliente: TestClient) -> None:
        """Leitura sem anotação do operador segue o caminho de recusa, não erro."""
        sem_rotulo = {k: v for k, v in EVENTO_DO_ENUNCIADO.items() if k != "fault"}
        resposta = cliente.post("/eventos/analisar", json=sem_rotulo)
        assert resposta.status_code == 200
        assert resposta.json()["caminho"] == "sem_documento"


class TestPrescricao:
    def test_resposta_completa(self, cliente: TestClient) -> None:
        corpo = cliente.post("/eventos/analisar", json=EVENTO_DO_ENUNCIADO).json()
        assert corpo["caminho"] == "prescricao"
        assert corpo["condicao"] == "cocked_rotor"
        assert corpo["documento"] == "Doc6"
        assert corpo["gerada_por_llm"] is True
        assert corpo["motivo_recusa"] is None

    def test_fontes_citadas(self, cliente: TestClient) -> None:
        """Rastreabilidade do ADR-004: toda prescrição aponta documento e seção."""
        fontes = cliente.post("/eventos/analisar", json=EVENTO_DO_ENUNCIADO).json()["fontes"]
        assert fontes
        for fonte in fontes:
            assert fonte["documento"]
            assert fonte["numero_secao"] > 0
            assert 0.0 <= fonte["relevancia"] <= 1.0

    def test_rotulo_bruto_preservado(self, cliente: TestClient) -> None:
        corpo = cliente.post("/eventos/analisar", json=EVENTO_DO_ENUNCIADO).json()
        assert corpo["rotulo_bruto"] == "cocked_rotor_2"


class TestRecusa:
    def test_defeito_sem_documento(self, cliente: TestClient) -> None:
        evento = EVENTO_DO_ENUNCIADO | {"fault": "new_falta_fase_0"}
        corpo = cliente.post("/eventos/analisar", json=evento).json()
        assert corpo["caminho"] == "sem_documento"
        assert corpo["motivo_recusa"] == "defeito_sem_documento"
        assert corpo["gerada_por_llm"] is False
        assert corpo["fontes"] == []
        assert "registre um documento" in corpo["recomendacao"].lower()

    def test_estado_do_sistema(self, cliente: TestClient) -> None:
        evento = EVENTO_DO_ENUNCIADO | {"fault": "normal_2"}
        corpo = cliente.post("/eventos/analisar", json=evento).json()
        assert corpo["caminho"] == "estado"
        assert corpo["motivo_recusa"] == "nao_e_defeito"
        assert "nenhum defeito" in corpo["recomendacao"].lower()

    def test_llm_nao_e_acionado_na_recusa(
        self, cliente: TestClient, cliente_llm: ClienteFalso
    ) -> None:
        """A garantia central do projeto, verificada no nível HTTP."""
        cliente.post("/eventos/analisar", json=EVENTO_DO_ENUNCIADO | {"fault": "ventoinha_2"})
        assert cliente_llm.chamadas == []

    def test_contexto_historico_presente_mesmo_na_recusa(self, cliente: TestClient) -> None:
        """Sem prescrição a dar, saber a frequência do padrão ainda é útil."""
        evento = EVENTO_DO_ENUNCIADO | {"fault": "new_falta_fase_0"}
        corpo = cliente.post("/eventos/analisar", json=evento).json()
        assert corpo["contexto"]["total_ocorrencias_similares"] > 0


class TestContextoHistorico:
    @pytest.fixture
    def contexto(self, cliente: TestClient) -> dict:
        return cliente.post("/eventos/analisar", json=EVENTO_DO_ENUNCIADO).json()["contexto"]

    def test_quantidade_de_ocorrencias(self, contexto: dict) -> None:
        assert contexto["total_ocorrencias_similares"] == 14275

    def test_frequencia_arredondada(self, contexto: dict) -> None:
        assert contexto["ocorrencias_por_condicao"][0]["frequencia_diaria"] == 2039.29

    def test_distribuicao_temporal_serializavel(self, contexto: dict) -> None:
        """Chaves do índice temporal viram texto ISO — Timestamp não é chave JSON."""
        assert contexto["distribuicao_temporal"] == {"2026-06-01": 42}

    def test_vizinho_declara_sua_condicao(self, contexto: dict) -> None:
        vizinho = contexto["vizinhos"][0]
        assert vizinho["condicao"] == "cocked_rotor"
        assert vizinho["similaridade"] == 0.974
        assert datetime.fromisoformat(vizinho["created_at"])


class TestDocumentacao:
    def test_openapi_disponivel(self, cliente: TestClient) -> None:
        """Diferencial 'APIs': o contrato é publicado, não descrito em prosa."""
        esquema = cliente.get("/openapi.json").json()
        assert "/eventos/analisar" in esquema["paths"]

    def test_exemplo_no_esquema(self, cliente: TestClient) -> None:
        esquema = cliente.get("/openapi.json").json()
        evento = esquema["components"]["schemas"]["EventoSensor"]
        assert evento["example"]["fault"] == "cocked_rotor_2"
