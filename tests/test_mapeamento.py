"""Testes do mapa defeito → documento (ADR-010, ADR-011).

Este mapa é a primeira barreira do guardrail. Um erro aqui é um erro de segurança do
sistema: ou o técnico recebe prescrição sem respaldo, ou fica sem resposta que existe.
"""

import pytest

from src.ingestion.rotulos import DEFEITOS, ESTADOS, normalizar
from src.rag.mapeamento import (
    JUSTIFICATIVAS,
    MAPA,
    cobertura,
    condicoes_documentadas,
    condicoes_sem_documento,
    validar_mapa,
)


class TestConsistencia:
    def test_mapa_cobre_a_taxonomia(self) -> None:
        validar_mapa()

    def test_toda_familia_de_defeito_esta_no_mapa(self) -> None:
        assert set(MAPA) == DEFEITOS

    def test_toda_condicao_sem_documento_tem_justificativa(self) -> None:
        assert condicoes_sem_documento() <= set(JUSTIFICATIVAS)

    def test_justificativas_sao_explicativas(self) -> None:
        """O texto acompanha a recusa: o técnico precisa entender o que cadastrar."""
        for condicao, texto in JUSTIFICATIVAS.items():
            assert len(texto) > 80, condicao


class TestRoteamento:
    @pytest.mark.parametrize(
        ("condicao", "documento"),
        [
            ("rolamento_inner", "Doc1"),
            ("rolamento_outer", "Doc1"),
            ("rolamento_ball", "Doc1"),
            ("rolamento_combination", "Doc1"),
            ("desalinhado", "Doc2"),
            ("desbalanceado", "Doc3"),
            ("correia", "Doc4"),
            ("polia", "Doc5"),
            ("cocked_rotor", "Doc6"),
        ],
    )
    def test_defeitos_documentados(self, condicao: str, documento: str) -> None:
        resultado = cobertura(condicao)
        assert resultado.documentada
        assert resultado.documento == documento

    def test_as_quatro_familias_de_rolamento_compartilham_o_doc1(self) -> None:
        """Doc1 é o único procedimento de rolamentos e cobre 40% dos defeitos."""
        rolamentos = {c for c in DEFEITOS if c.startswith("rolamento_")}
        assert {MAPA[c] for c in rolamentos} == {"Doc1"}

    def test_rotulo_bruto_roteia_pela_forma_canonica(self) -> None:
        """O caminho completo: rótulo do operador → condição canônica → documento."""
        assert cobertura(normalizar("cocked_rotor_2").canonico).documento == "Doc6"
        assert cobertura(normalizar("cockecocked_adxl_0").canonico).documento == "Doc6"


class TestRecusa:
    @pytest.mark.parametrize("condicao", ["falta_fase", "ventoinha", "eccentric_rotor"])
    def test_defeitos_sem_documento(self, condicao: str) -> None:
        resultado = cobertura(condicao)
        assert not resultado.documentada
        assert resultado.documento is None
        assert resultado.justificativa

    def test_falta_fase_e_falha_eletrica(self) -> None:
        """Melhor caso de demonstração do guardrail: os seis procedimentos são
        mecânicos, e não há como argumentar que algum deles cobriria falha elétrica."""
        assert "elétrica" in cobertura("falta_fase").justificativa

    def test_eccentric_rotor_recusa_documentacao_adjacente(self) -> None:
        """ADR-011: o Doc5 trata excentricidade de polia, não de rotor. Aceitá-lo seria
        prescrever intervenção no componente errado."""
        justificativa = cobertura("eccentric_rotor").justificativa
        assert "polia" in justificativa.lower()
        assert "rotor" in justificativa.lower()

    def test_condicao_desconhecida(self) -> None:
        resultado = cobertura("cavitacao")
        assert not resultado.documentada
        assert resultado.justificativa


class TestEstados:
    @pytest.mark.parametrize("estado", sorted(ESTADOS))
    def test_estado_nao_e_defeito_sem_documento(self, estado: str) -> None:
        """ADR-006: estado segue um terceiro caminho. Dizer 'não há documento para
        normal' afirmaria que `normal` é um defeito."""
        resultado = cobertura(estado)
        assert not resultado.documentada
        assert "não" in resultado.justificativa.lower()
        assert "corrigir" in resultado.justificativa.lower()


class TestCobertura:
    def test_proporcao_documentada(self) -> None:
        assert len(condicoes_documentadas()) == 9
        assert len(condicoes_sem_documento()) == 3
