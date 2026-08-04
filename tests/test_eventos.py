"""Testes de carga dos eventos, executados sobre a amostra versionada.

A amostra é estratificada por rótulo bruto e contém os 151 rótulos do conjunto completo,
inclusive os erros de digitação — portanto exercita a normalização contra dados reais,
não contra exemplos escolhidos a dedo.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.eventos import ATRIBUTOS, REDUNDANTES, apenas_defeitos, carregar_eventos

AMOSTRA = Path(__file__).resolve().parents[1] / "data" / "amostra_banner.csv"


@pytest.fixture(scope="module")
def eventos() -> pd.DataFrame:
    if not AMOSTRA.exists():
        pytest.skip("amostra ausente: rode scripts/gerar_amostra.py")
    return carregar_eventos(AMOSTRA)


class TestCarga:
    def test_colunas_redundantes_descartadas(self, eventos: pd.DataFrame) -> None:
        assert not set(REDUNDANTES) & set(eventos.columns)

    def test_atributos_presentes(self, eventos: pd.DataFrame) -> None:
        assert set(ATRIBUTOS) <= set(eventos.columns)
        assert len(ATRIBUTOS) == 16

    def test_created_at_e_temporal(self, eventos: pd.DataFrame) -> None:
        assert pd.api.types.is_datetime64_any_dtype(eventos["created_at"])

    def test_sem_valores_ausentes_nos_atributos(self, eventos: pd.DataFrame) -> None:
        assert eventos[list(ATRIBUTOS)].isna().sum().sum() == 0

    def test_arquivo_inexistente_orienta_o_download(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="README"):
            carregar_eventos(tmp_path / "ausente.csv")


class TestCondicaoCanonica:
    def test_nenhum_rotulo_fica_desconhecido(self, eventos: pd.DataFrame) -> None:
        """Se este teste falhar, o guardrail passará a recusar eventos documentados."""
        desconhecidos = eventos[eventos["tipo_condicao"] == "desconhecido"]
        assert desconhecidos.empty, sorted(desconhecidos["fault"].unique())

    def test_taxonomia_colapsa_para_17_condicoes(self, eventos: pd.DataFrame) -> None:
        assert eventos["fault"].nunique() == 151
        assert eventos["condicao"].nunique() == 17

    def test_proporcao_defeito_estado(self, eventos: pd.DataFrame) -> None:
        """No conjunto completo, 90,6% dos eventos são defeitos. A amostra é
        estratificada por rótulo com piso mínimo, então a proporção desloca-se um pouco
        em favor dos rótulos raros — mas a ordem de grandeza deve se manter."""
        proporcao = (eventos["tipo_condicao"] == "defeito").mean()
        assert 0.80 < proporcao < 0.95

    def test_defeitos_conhecidos_presentes(self, eventos: pd.DataFrame) -> None:
        condicoes = set(eventos["condicao"])
        assert {"falta_fase", "eccentric_rotor", "ventoinha"} <= condicoes

    def test_apenas_defeitos_exclui_estados(self, eventos: pd.DataFrame) -> None:
        defeitos = apenas_defeitos(eventos)
        assert set(defeitos["tipo_condicao"]) == {"defeito"}
        assert "normal" not in set(defeitos["condicao"])


class TestSaturacaoKurtosis:
    def test_marcacao_existe(self, eventos: pd.DataFrame) -> None:
        assert eventos["kurtosis_saturada"].dtype == bool

    def test_marca_leitura_no_limite_do_registrador(self) -> None:
        """65,535 = 2¹⁶ − 1: estouro do registrador uint16 do sensor, não valor físico."""
        bruto = pd.read_csv(AMOSTRA, nrows=1)
        bruto.loc[0, "z_kurtosis"] = 65.535
        destino = AMOSTRA.parent / "_saturado.csv"
        bruto.to_csv(destino, index=False)
        try:
            assert carregar_eventos(destino)["kurtosis_saturada"].iloc[0]
        finally:
            destino.unlink()
