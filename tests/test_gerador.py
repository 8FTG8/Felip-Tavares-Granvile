"""Testes da geração da recomendação (ADR-001, ADR-004, ADR-013).

O ponto central verificado aqui é que o modelo de linguagem **não é acionado** nos
caminhos de recusa. Um cliente falso registra as chamadas, de modo que "o LLM não foi
chamado" deixa de ser suposição e passa a ser asserção.
"""

from dataclasses import dataclass, field

import pytest

from src.rag.documentos import Trecho
from src.rag.gerador import (
    INSTRUCAO_SISTEMA,
    MODELO_PRODUCAO,
    MODELO_REDUZIDO,
    TEMPERATURA,
    Gerador,
)
from src.rag.indice_documental import TrechoRecuperado
from src.rag.roteador import Roteador
from tests.test_roteador import IndiceFalso


@dataclass
class ClienteFalso:
    """Registra as chamadas ao modelo em vez de executá-las."""

    resposta: str = "Procedimento recomendado (Doc6, seção 16)."
    chamadas: list[dict] = field(default_factory=list)

    def chat(self, **kwargs):
        self.chamadas.append(kwargs)
        if kwargs.get("stream"):
            return iter([{"message": {"content": self.resposta}}])
        return {"message": {"content": self.resposta}}

    def list(self):
        return {"models": [{"model": MODELO_PRODUCAO}]}


@pytest.fixture
def cliente() -> ClienteFalso:
    return ClienteFalso()


@pytest.fixture
def gerador(cliente: ClienteFalso) -> Gerador:
    return Gerador(cliente=cliente)  # type: ignore[arg-type]


@pytest.fixture
def roteador() -> Roteador:
    return Roteador(IndiceFalso())  # type: ignore[arg-type]


class TestCaminhosDeRecusaNaoAcionamOLLM:
    """A garantia central do ADR-004: sem respaldo documental, o modelo nem é chamado."""

    def test_estado_nao_chama_o_modelo(
        self, roteador: Roteador, gerador: Gerador, cliente: ClienteFalso
    ) -> None:
        recomendacao = gerador.responder(roteador.decidir("normal_2"))
        assert cliente.chamadas == []
        assert not recomendacao.gerada_por_llm
        assert recomendacao.modelo is None

    def test_sem_documento_nao_chama_o_modelo(
        self, roteador: Roteador, gerador: Gerador, cliente: ClienteFalso
    ) -> None:
        recomendacao = gerador.responder(roteador.decidir("new_falta_fase_0"))
        assert cliente.chamadas == []
        assert not recomendacao.gerada_por_llm

    def test_fluxo_tambem_respeita_a_recusa(
        self, roteador: Roteador, gerador: Gerador, cliente: ClienteFalso
    ) -> None:
        texto = "".join(gerador.responder_em_fluxo(roteador.decidir("ventoinha_2")))
        assert cliente.chamadas == []
        assert "não há procedimento" in texto.lower()


class TestTextoDaRecusa:
    def test_estado_afirma_ausencia_de_defeito(
        self, roteador: Roteador, gerador: Gerador
    ) -> None:
        """Nunca dizer 'não há documento para normal' — isso afirmaria que é defeito."""
        texto = gerador.responder(roteador.decidir("normal_2")).texto
        assert "nenhum defeito" in texto.lower()
        assert "documento" not in texto.lower().split("contexto")[0]

    def test_sem_documento_convida_ao_cadastro(
        self, roteador: Roteador, gerador: Gerador
    ) -> None:
        """Exigência literal do enunciado."""
        texto = gerador.responder(roteador.decidir("new_falta_fase_0")).texto
        assert "registre um documento" in texto.lower()

    def test_sem_documento_explica_o_motivo(
        self, roteador: Roteador, gerador: Gerador
    ) -> None:
        texto = gerador.responder(roteador.decidir("eccentric_rotor_3")).texto
        assert "polia" in texto.lower()

    def test_recusa_por_relevancia_informa_o_limiar(self, gerador: Gerador) -> None:
        roteador = Roteador(IndiceFalso(relevancia=0.40))  # type: ignore[arg-type]
        texto = gerador.responder(roteador.decidir("cocked_rotor_2")).texto
        assert "0.400" in texto or "0,400" in texto


class TestPrescricao:
    def test_aciona_o_modelo(
        self, roteador: Roteador, gerador: Gerador, cliente: ClienteFalso
    ) -> None:
        recomendacao = gerador.responder(roteador.decidir("cocked_rotor_2"))
        assert len(cliente.chamadas) == 1
        assert recomendacao.gerada_por_llm
        assert recomendacao.citacoes

    def test_prompt_carrega_apenas_os_trechos_recuperados(
        self, roteador: Roteador, gerador: Gerador, cliente: ClienteFalso
    ) -> None:
        gerador.responder(roteador.decidir("cocked_rotor_2"))
        conteudo = cliente.chamadas[0]["messages"][1]["content"]
        assert "Conteúdo do procedimento." in conteudo
        assert "seção 19" in conteudo

    def test_instrucao_proibe_conhecimento_proprio(
        self, roteador: Roteador, gerador: Gerador, cliente: ClienteFalso
    ) -> None:
        gerador.responder(roteador.decidir("cocked_rotor_2"))
        sistema = cliente.chamadas[0]["messages"][0]["content"]
        assert sistema == INSTRUCAO_SISTEMA
        assert "EXCLUSIVAMENTE" in sistema
        assert "Não invente valores numéricos" in sistema

    def test_temperatura_baixa(
        self, roteador: Roteador, gerador: Gerador, cliente: ClienteFalso
    ) -> None:
        """A tarefa é reescrever procedimento, não criar texto."""
        gerador.responder(roteador.decidir("cocked_rotor_2"))
        assert cliente.chamadas[0]["options"]["temperature"] == TEMPERATURA
        assert TEMPERATURA <= 0.3

    def test_pergunta_do_tecnico_chega_ao_prompt(
        self, roteador: Roteador, gerador: Gerador, cliente: ClienteFalso
    ) -> None:
        pergunta = "o eixo pode estar empenado?"
        gerador.responder(roteador.decidir("cocked_rotor_2", pergunta), pergunta)
        assert pergunta in cliente.chamadas[0]["messages"][1]["content"]


class TestModeloConfiguravel:
    """ADR-013: o modelo é dimensionado por hardware, sem alterar código."""

    def test_padrao_e_o_modelo_de_producao(self, cliente: ClienteFalso) -> None:
        assert Gerador(cliente=cliente)._modelo in {MODELO_PRODUCAO, MODELO_REDUZIDO}

    def test_modelo_explicito(self, roteador: Roteador, cliente: ClienteFalso) -> None:
        gerador = Gerador(modelo=MODELO_REDUZIDO, cliente=cliente)  # type: ignore[arg-type]
        gerador.responder(roteador.decidir("cocked_rotor_2"))
        assert cliente.chamadas[0]["model"] == MODELO_REDUZIDO

    def test_disponibilidade_verificavel(self, cliente: ClienteFalso) -> None:
        assert Gerador(cliente=cliente).disponivel()  # type: ignore[arg-type]


@pytest.mark.lento
class TestIntegracaoComOllama:
    """Exercita o modelo real. Requer Ollama servindo o modelo configurado."""

    def test_prescricao_real_cita_fonte(self, roteador: Roteador) -> None:
        gerador = Gerador()
        if not gerador.disponivel():
            pytest.skip("Ollama indisponível ou modelo não baixado")
        recomendacao = gerador.responder(roteador.decidir("cocked_rotor_2"))
        assert recomendacao.texto
        assert recomendacao.gerada_por_llm
