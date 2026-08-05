"""Comportamento da API com o serviço de modelos fora do ar.

Este arquivo existe por causa de um achado durante a demonstração: com o Ollama parado,
a prescrição devolvia **500** e a interface exibia "A API não está respondendo" — que era
falso, porque a API respondeu; quem não respondeu foi o modelo. O operador era mandado
reiniciar o processo errado.

Há duas asserções aqui, e a segunda importa mais que a primeira:

1. o caminho de prescrição devolve 503 com mensagem própria e ``Retry-After``;
2. **os caminhos de recusa continuam devolvendo 200** com o modelo derrubado.

A segunda é o ADR-004 se verificando sob falha: como os textos de recusa são compostos em
código e nunca gerados, derrubar o modelo não deveria afetá-los. Se um dia afetar, é
porque alguém passou a gerar o que precisava ser determinístico — e este teste falha.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencias import (
    obter_gerador,
    obter_indice_similaridade,
    obter_roteador,
)
from src.rag.gerador import Gerador, ModeloIndisponivel
from src.rag.roteador import Roteador
from tests.test_api_eventos import SimilaridadeFalsa
from tests.test_indice import EVENTO_DO_ENUNCIADO
from tests.test_roteador import IndiceFalso


class OllamaParado:
    """Recusa qualquer conexão, como o cliente real faz quando o serviço não subiu."""

    erro = ConnectionRefusedError("[WinError 10061] a máquina de destino recusou")

    def chat(self, **kwargs):
        raise self.erro

    def list(self):
        raise self.erro


class ModeloNaoBaixado:
    """O serviço responde, mas não tem o modelo configurado."""

    def chat(self, **kwargs):
        raise RuntimeError("model not found")

    def list(self):
        return {"models": [{"model": "llama3:8b"}]}


class SimilaridadeComTotal(SimilaridadeFalsa):
    """`GET /sistema` publica o tamanho do índice, que o dublê original não expõe."""

    total_eventos = 166796


def _cliente_http(cliente_llm) -> TestClient:
    app.dependency_overrides[obter_indice_similaridade] = lambda: SimilaridadeComTotal()
    app.dependency_overrides[obter_roteador] = lambda: Roteador(IndiceFalso())
    app.dependency_overrides[obter_gerador] = lambda: Gerador(cliente=cliente_llm)
    return TestClient(app)


@pytest.fixture
def http() -> TestClient:
    cliente = _cliente_http(OllamaParado())
    yield cliente
    app.dependency_overrides.clear()


@pytest.fixture
def http_sem_modelo() -> TestClient:
    cliente = _cliente_http(ModeloNaoBaixado())
    yield cliente
    app.dependency_overrides.clear()


class TestPrescricaoDevolve503:
    """500 diria ao integrador que o serviço tem defeito; 503, que a dependência caiu."""

    def test_analise_de_evento(self, http: TestClient) -> None:
        resposta = http.post("/eventos/analisar", json=EVENTO_DO_ENUNCIADO)
        assert resposta.status_code == 503

    def test_traz_retry_after(self, http: TestClient) -> None:
        """503 é retentável por convenção, e o cabeçalho diz em quanto tempo."""
        resposta = http.post("/eventos/analisar", json=EVENTO_DO_ENUNCIADO)
        assert resposta.headers["Retry-After"] == "10"

    def test_mensagem_aponta_o_servico_certo(self, http: TestClient) -> None:
        """A mensagem antiga mandava subir a API, que estava no ar o tempo todo."""
        detalhe = http.post("/eventos/analisar", json=EVENTO_DO_ENUNCIADO).json()["detail"]
        assert "Ollama" in detalhe
        assert "ollama serve" in detalhe

    def test_chat(self, http: TestClient) -> None:
        resposta = http.post("/chat", json={"condicao": "cocked_rotor", "pergunta": "como corrijo?"})
        assert resposta.status_code == 503

    def test_fluxo_falha_antes_dos_cabecalhos(self, http: TestClient) -> None:
        """O ponto sensível do desenho.

        A geração em fluxo é preguiçosa: se a verificação só acontecesse ao puxar o
        primeiro pedaço, os cabeçalhos — e portanto o status 200 — já teriam sido
        enviados, e não haveria mais como devolver 503. Por isso a checagem é feita na
        chamada, e não dentro do gerador.
        """
        resposta = http.post(
            "/chat/fluxo", json={"condicao": "cocked_rotor", "pergunta": "como corrijo?"}
        )
        assert resposta.status_code == 503

    def test_modelo_ausente_pede_o_download(self, http_sem_modelo: TestClient) -> None:
        """Serviço no ar e modelo faltando é outro problema, com outra ação corretiva."""
        detalhe = http_sem_modelo.post("/eventos/analisar", json=EVENTO_DO_ENUNCIADO).json()
        assert "ollama pull" in detalhe["detail"]


class TestRecusasSobrevivemAoModeloFora:
    """O ADR-004 verificado sob falha: o que é composto em código não depende do LLM."""

    def test_defeito_sem_documento_responde_200(self, http: TestClient) -> None:
        evento = EVENTO_DO_ENUNCIADO | {"fault": "new_falta_fase_0"}
        resposta = http.post("/eventos/analisar", json=evento)
        assert resposta.status_code == 200
        assert resposta.json()["caminho"] == "sem_documento"
        assert resposta.json()["gerada_por_llm"] is False

    def test_estado_operacional_responde_200(self, http: TestClient) -> None:
        evento = EVENTO_DO_ENUNCIADO | {"fault": "normal_2"}
        resposta = http.post("/eventos/analisar", json=evento)
        assert resposta.status_code == 200
        assert resposta.json()["caminho"] == "estado"

    def test_recusa_traz_o_texto_completo(self, http: TestClient) -> None:
        """Não é um 200 vazio: a recusa que o enunciado pede chega inteira."""
        evento = EVENTO_DO_ENUNCIADO | {"fault": "new_falta_fase_0"}
        recomendacao = http.post("/eventos/analisar", json=evento).json()["recomendacao"]
        assert len(recomendacao) > 80

    def test_contexto_historico_continua_disponivel(self, http: TestClient) -> None:
        """A busca por similaridade não passa pelo modelo e segue respondendo."""
        evento = EVENTO_DO_ENUNCIADO | {"fault": "new_falta_fase_0"}
        contexto = http.post("/eventos/analisar", json=evento).json()["contexto"]
        assert contexto["total_ocorrencias_similares"] > 0

    def test_fluxo_de_recusa_responde_200(self, http: TestClient) -> None:
        resposta = http.post(
            "/chat/fluxo", json={"condicao": "falta_fase", "pergunta": "como corrijo?"}
        )
        assert resposta.status_code == 200
        assert resposta.headers["X-Caminho"] == "sem_documento"

    def test_sistema_reporta_o_modelo_como_indisponivel(self, http: TestClient) -> None:
        """A informação já existia; o que faltava era a requisição consultá-la."""
        assert http.get("/sistema").json()["modelo_disponivel"] is False


class TestDisponibilidade:
    def test_verificar_levanta_com_servico_parado(self) -> None:
        with pytest.raises(ModeloIndisponivel, match="ollama serve"):
            Gerador(cliente=OllamaParado()).verificar()

    def test_verificar_levanta_com_modelo_ausente(self) -> None:
        with pytest.raises(ModeloIndisponivel, match="ollama pull"):
            Gerador(cliente=ModeloNaoBaixado()).verificar()
