"""Testes do roteamento e das barreiras anti-alucinação (ADR-004, ADR-006, ADR-010).

Estes são os testes mais importantes do projeto: eles verificam *quando* o sistema se
recusa a responder. A maioria usa um índice documental falso, porque o comportamento sob
teste é determinístico e não deve depender do modelo de embeddings — se a decisão de
recusar exigisse carregar 1,1 GB de pesos para ser verificada, ela não seria
determinística.
"""

from dataclasses import dataclass, field

import pytest

from src.ingestion.rotulos import ESTADOS
from src.rag.documentos import Trecho
from src.rag.indice_documental import TrechoRecuperado
from src.rag.roteador import (
    LIMIAR_RELEVANCIA,
    Caminho,
    MotivoRecusa,
    Roteador,
)


@dataclass
class IndiceFalso:
    """Índice controlável: devolve trechos com a relevância que o teste determinar."""

    relevancia: float = 0.95
    documento_devolvido: str | None = None
    indexados: list = field(default_factory=list)

    def indexar(self, trechos=None, recriar: bool = False) -> int:
        """Registra o que seria indexado, sem carregar o modelo de embeddings."""
        self.indexados.extend(trechos or [])
        return len(trechos or [])

    def buscar(self, pergunta: str, documento: str | None = None, trechos: int = 4):
        self.documento_devolvido = documento
        return [
            TrechoRecuperado(
                trecho=Trecho(
                    documento=documento or "Doc1",
                    titulo_documento="Procedimento de teste",
                    numero_secao=19,
                    titulo_secao="Correção da Falha",
                    texto="Conteúdo do procedimento.",
                    origem="nativo",
                ),
                relevancia=self.relevancia,
            )
        ]


@pytest.fixture
def indice() -> IndiceFalso:
    return IndiceFalso()


@pytest.fixture
def roteador(indice: IndiceFalso) -> Roteador:
    return Roteador(indice)  # type: ignore[arg-type]


class TestCaminhoEstado:
    """ADR-006: estado não é defeito e não é 'defeito sem documento'."""

    @pytest.mark.parametrize("rotulo", ["normal", "normal_2", "motor_desligado", "acelerando"])
    def test_estados_seguem_caminho_proprio(self, roteador: Roteador, rotulo: str) -> None:
        decisao = roteador.decidir(rotulo)
        assert decisao.caminho is Caminho.ESTADO
        assert decisao.motivo is MotivoRecusa.NAO_E_DEFEITO
        assert not decisao.deve_gerar

    def test_new_baseline_e_estado(self, roteador: Roteador) -> None:
        """`baseline` só existe como `new_baseline` no conjunto; uma comparação literal
        com a lista do enunciado o trataria como defeito."""
        assert roteador.decidir("new_baseline").caminho is Caminho.ESTADO

    def test_todos_os_estados_da_taxonomia(self, roteador: Roteador) -> None:
        for estado in ESTADOS:
            assert roteador.decidir(estado).caminho is Caminho.ESTADO

    def test_estado_nao_consulta_o_indice(self, roteador: Roteador, indice: IndiceFalso) -> None:
        """A decisão é anterior a qualquer busca."""
        roteador.decidir("normal")
        assert indice.documento_devolvido is None


class TestPrimeiraBarreira:
    """Mapa defeito → documento: consulta a dicionário, sem modelo envolvido."""

    @pytest.mark.parametrize(
        ("rotulo", "documento"),
        [
            ("cocked_rotor_2", "Doc6"),
            ("rolamento_inner_pos_2", "Doc1"),
            ("desalinhado_3", "Doc2"),
            ("cockecocked_adxl_0", "Doc6"),
        ],
    )
    def test_defeito_documentado_prossegue(
        self, roteador: Roteador, rotulo: str, documento: str
    ) -> None:
        decisao = roteador.decidir(rotulo)
        assert decisao.caminho is Caminho.PRESCRICAO
        assert decisao.documento == documento
        assert decisao.deve_gerar

    @pytest.mark.parametrize("rotulo", ["new_falta_fase_0", "ventoinha_2", "eccentric_rotor_3"])
    def test_defeito_sem_documento_e_barrado(self, roteador: Roteador, rotulo: str) -> None:
        decisao = roteador.decidir(rotulo)
        assert decisao.caminho is Caminho.SEM_DOCUMENTO
        assert decisao.motivo is MotivoRecusa.DEFEITO_SEM_DOCUMENTO
        assert not decisao.deve_gerar
        assert decisao.cobertura.justificativa

    def test_barreira_nao_consulta_o_indice(
        self, roteador: Roteador, indice: IndiceFalso
    ) -> None:
        """Sem documento mapeado, nem a busca semântica chega a acontecer."""
        roteador.decidir("new_falta_fase_0")
        assert indice.documento_devolvido is None

    def test_condicao_desconhecida(self, roteador: Roteador) -> None:
        decisao = roteador.decidir("cavitacao_severa")
        assert decisao.caminho is Caminho.SEM_DOCUMENTO
        assert decisao.motivo is MotivoRecusa.CONDICAO_DESCONHECIDA

    def test_rotulo_ausente(self, roteador: Roteador) -> None:
        assert roteador.decidir(None).caminho is Caminho.SEM_DOCUMENTO


class TestSegundaBarreira:
    """Limiar de relevância: documento existe, mas nenhuma seção responde à pergunta."""

    def test_trecho_irrelevante_bloqueia(self) -> None:
        roteador = Roteador(IndiceFalso(relevancia=0.60))  # type: ignore[arg-type]
        decisao = roteador.decidir("cocked_rotor_2", "como calibrar o transmissor de pressão")
        assert decisao.caminho is Caminho.SEM_DOCUMENTO
        assert decisao.motivo is MotivoRecusa.SEM_TRECHO_RELEVANTE
        assert decisao.relevancia_maxima == pytest.approx(0.60)

    def test_trecho_relevante_libera(self) -> None:
        roteador = Roteador(IndiceFalso(relevancia=0.90))  # type: ignore[arg-type]
        assert roteador.decidir("cocked_rotor_2").caminho is Caminho.PRESCRICAO

    def test_limiar_exato_e_aceito(self) -> None:
        roteador = Roteador(IndiceFalso(relevancia=LIMIAR_RELEVANCIA))  # type: ignore[arg-type]
        assert roteador.decidir("cocked_rotor_2").caminho is Caminho.PRESCRICAO

    def test_limiar_calibrado_e_nao_arbitrario(self) -> None:
        """ADR-010: o valor vem de scripts/calibrar_limiar.py, que mediu 44 perguntas —
        longas e curtas, pertinentes e não. As distribuições se sobrepõem, e o corte é o
        piso que aceita todas as legítimas medidas (mínima observada: 0,8407)."""
        assert LIMIAR_RELEVANCIA <= 0.8407

    def test_limiar_configuravel(self) -> None:
        permissivo = Roteador(IndiceFalso(relevancia=0.50), limiar=0.10)  # type: ignore[arg-type]
        assert permissivo.decidir("cocked_rotor_2").caminho is Caminho.PRESCRICAO


class TestFiltroPorDocumento:
    def test_busca_restrita_ao_documento_roteado(
        self, roteador: Roteador, indice: IndiceFalso
    ) -> None:
        """A busca nunca percorre a base inteira no fluxo de prescrição."""
        roteador.decidir("rolamento_ball_2")
        assert indice.documento_devolvido == "Doc1"


class TestPerguntaPadrao:
    def test_evento_sem_pergunta_gera_consulta_derivada(self, roteador: Roteador) -> None:
        """Evento vindo do sensor não tem pergunta associada."""
        assert roteador.decidir("polia_2").caminho is Caminho.PRESCRICAO


class TestRastreabilidade:
    def test_decisao_preserva_rotulo_bruto_e_canonico(self, roteador: Roteador) -> None:
        decisao = roteador.decidir("cockecocked_adxl_0")
        assert decisao.rotulo_bruto == "cockecocked_adxl_0"
        assert decisao.condicao == "cocked_rotor"

    def test_citacoes_disponiveis_na_prescricao(self, roteador: Roteador) -> None:
        decisao = roteador.decidir("cocked_rotor_2")
        assert decisao.citacoes
        assert "seção 19" in decisao.citacoes[0]

    def test_recusa_nao_tem_citacoes(self, roteador: Roteador) -> None:
        assert roteador.decidir("new_falta_fase_0").citacoes == []
