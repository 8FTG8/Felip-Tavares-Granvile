"""Testes da normalização canônica de rótulos (ADR-005).

O foco está nos casos que, se falharem, fazem o guardrail recusar atendimento a eventos
que possuem documentação — a falha mais cara do projeto.
"""

import pytest

from src.ingestion.rotulos import (
    DEFEITOS,
    DESCONHECIDO,
    ESTADOS,
    TipoCondicao,
    e_defeito,
    normalizar,
)


class TestErrosDeDigitacao:
    """Os 10 erros do operador precisam chegar à família correta.

    São 421 eventos que possuem documentação e seriam recusados sem esta correção.
    """

    @pytest.mark.parametrize(
        ("bruto", "esperado"),
        [
            ("desbalanceamento", "desbalanceado"),
            ("desabalanceado_3", "desbalanceado"),
            ("desbanlanceado_carga_3_2", "desbalanceado"),
            ("ddesbalanceado_adxl_0", "desbalanceado"),
            ("dedesbalanceado_adxl_1", "desbalanceado"),
            ("new_desabanceado_1", "desbalanceado"),
            ("cockecocked_adxl_0", "cocked_rotor"),
            ("normla_carga_3_3", "normal"),
            ("mortor_desligado_novo", "motor_desligado"),
            ("new_tes", "teste"),
        ],
    )
    def test_typo_chega_a_familia_correta(self, bruto: str, esperado: str) -> None:
        assert normalizar(bruto).canonico == esperado

    def test_desalinhado_nao_colapsa_em_desbalanceado(self) -> None:
        """Os dois estão a poucas edições um do outro; confundi-los rotearia o
        técnico ao documento errado."""
        assert normalizar("desalinhado").canonico == "desalinhado"
        assert normalizar("desbalanceado").canonico == "desbalanceado"


class TestEstados:
    """Estados não são defeitos e seguem o terceiro caminho de resposta (ADR-006)."""

    def test_baseline_existe_apenas_como_new_baseline(self) -> None:
        """O único registro de ``baseline`` no conjunto é ``new_baseline`` (69
        eventos). Uma regra por igualdade exata contra a lista do enunciado os trataria
        como defeito."""
        condicao = normalizar("new_baseline")
        assert condicao.canonico == "baseline"
        assert condicao.tipo is TipoCondicao.ESTADO

    @pytest.mark.parametrize(
        "bruto",
        ["normal", "normal_2", "normal_pos_2", "normal_carga_3_2", "normal_adxl_1", "new_normal_6"],
    )
    def test_variantes_de_normal(self, bruto: str) -> None:
        condicao = normalizar(bruto)
        assert condicao.canonico == "normal"
        assert not condicao.e_defeito

    def test_sufixo_novo_teste_e_sessao_nao_estado(self) -> None:
        """``rolamento_outer_novo_teste`` é um rolamento coletado em novo teste, não o
        estado ``teste``."""
        assert normalizar("rolamento_outer_novo_teste").canonico == "rolamento_outer"
        assert normalizar("normal_novo_teste").canonico == "normal"
        assert normalizar("teste").canonico == "teste"

    def test_todos_os_estados_classificados_como_estado(self) -> None:
        for estado in ESTADOS:
            assert normalizar(estado).tipo is TipoCondicao.ESTADO


class TestSufixosDeSessao:
    @pytest.mark.parametrize(
        ("bruto", "esperado"),
        [
            ("rolamento_inner_2", "rolamento_inner"),
            ("rolamento_inner_pos_2", "rolamento_inner"),
            ("rolamento_inner_carga_2", "rolamento_inner"),
            ("rolamento_outer_adxl_0", "rolamento_outer"),
            ("rolamento_outer_novo", "rolamento_outer"),
            ("eccentric_rotor_2_pos_2", "eccentric_rotor"),
            ("new_desbalanceado_antigo_3", "desbalanceado"),
            ("desbalanceado_carga_3_2", "desbalanceado"),
        ],
    )
    def test_sufixos_removidos(self, bruto: str, esperado: str) -> None:
        assert normalizar(bruto).canonico == esperado

    @pytest.mark.parametrize(
        ("bruto", "esperado"),
        [
            ("rolamento_comb_adxl_0", "rolamento_combination"),
            ("new_rolamento_comb_3", "rolamento_combination"),
            ("new_cocked_0", "cocked_rotor"),
            ("cocked_adxl_0", "cocked_rotor"),
            ("new_eccentric_2", "eccentric_rotor"),
            ("eccentric_2_pos_2", "eccentric_rotor"),
            ("eccentric_adxl_0", "eccentric_rotor"),
            ("desbalanceado_1parafuso", "desbalanceado"),
            ("new_falta_fase_0", "falta_fase"),
        ],
    )
    def test_abreviacoes_e_variantes(self, bruto: str, esperado: str) -> None:
        assert normalizar(bruto).canonico == esperado


class TestRotuloDesconhecido:
    """Condição nova cai no caminho de recusa (ADR-006) — comportamento desejado."""

    @pytest.mark.parametrize("bruto", ["cavitacao", "", "   ", "folga_mecanica_3"])
    def test_desconhecido(self, bruto: str) -> None:
        condicao = normalizar(bruto)
        assert condicao.canonico == DESCONHECIDO
        assert condicao.tipo is TipoCondicao.DESCONHECIDO
        assert not condicao.e_defeito

    def test_none(self) -> None:
        assert normalizar(None).tipo is TipoCondicao.DESCONHECIDO


class TestContrato:
    def test_taxonomia_tem_17_condicoes(self) -> None:
        assert len(DEFEITOS) == 12
        assert len(ESTADOS) == 5
        assert not DEFEITOS & ESTADOS

    def test_normalizacao_e_idempotente(self) -> None:
        """A forma canônica normalizada em si mesma não muda — garante que o
        roteamento documental pode ser aplicado em qualquer ponto do pipeline."""
        for condicao in DEFEITOS | ESTADOS:
            assert normalizar(condicao).canonico == condicao

    def test_preserva_o_rotulo_bruto(self) -> None:
        """Rastreabilidade: a resposta ao usuário mostra o que o operador anotou."""
        assert normalizar("cockecocked_adxl_0").bruto == "cockecocked_adxl_0"

    def test_atalho_e_defeito(self) -> None:
        assert e_defeito("cocked_rotor_2")
        assert not e_defeito("normal_2")
        assert not e_defeito("cavitacao")

    def test_condicao_e_imutavel(self) -> None:
        with pytest.raises(AttributeError):
            normalizar("normal").canonico = "outro"  # type: ignore[misc]

    def test_case_insensitive(self) -> None:
        assert normalizar("Cocked_Rotor_2").canonico == "cocked_rotor"
        assert normalizar("  NORMAL  ").canonico == "normal"
