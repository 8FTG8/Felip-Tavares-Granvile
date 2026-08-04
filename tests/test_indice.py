"""Testes da busca por similaridade (ADR-003, ADR-007, ADR-008)."""

from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.eventos import ATRIBUTOS, carregar_eventos
from src.similarity.indice import IndiceSimilaridade

AMOSTRA = Path(__file__).resolve().parents[1] / "data" / "amostra_banner.csv"

#: Evento de entrada exatamente como aparece no enunciado, com as colunas redundantes
#: que a solução ignora. Corresponde ao id 114387 do conjunto completo.
EVENTO_DO_ENUNCIADO = {
    "id": 114387,
    "created_at": "2026-06-01 21:32:53.911176+00:00",
    "z_rms_velocity_in_s": 0.0597,
    "z_rms_velocity_mm_s": 1.517,
    "temperature_f": 76.44,
    "temperature_c": 24.69,
    "x_rms_velocity_in_s": 0.0787,
    "x_rms_velocity_mm_s": 2.0,
    "z_peak_acceleration_g": 0.484,
    "x_peak_acceleration_g": 0.631,
    "z_peak_vel_comp_freq_hz": 61.0,
    "x_peak_vel_comp_freq_hz": 61.0,
    "z_rms_acceleration_g": 0.09,
    "x_rms_acceleration_g": 0.114,
    "z_kurtosis": 2.392,
    "x_kurtosis": 2.77,
    "z_crest_factor": 3.747,
    "x_crest_factor": 4.269,
    "z_peak_velocity_in_s": 0.0844,
    "z_peak_velocity_mm_s": 2.146,
    "x_peak_velocity_in_s": 0.1113,
    "x_peak_velocity_mm_s": 2.829,
    "z_high_freq_rms_accel_g": 0.129,
    "x_high_freq_rms_accel_g": 0.147,
    "fault": "cocked_rotor_2",
    "rpm": 1000.0,
}


@pytest.fixture(scope="module")
def eventos() -> pd.DataFrame:
    if not AMOSTRA.exists():
        pytest.skip("amostra ausente: rode scripts/gerar_amostra.py")
    return carregar_eventos(AMOSTRA)


@pytest.fixture(scope="module")
def indice(eventos: pd.DataFrame) -> IndiceSimilaridade:
    return IndiceSimilaridade(eventos, vizinhos=10)


class TestConstrucao:
    def test_deduplica_vetores_identicos(self, indice: IndiceSimilaridade) -> None:
        """O índice guarda vetores distintos; as contagens usam o histórico completo."""
        assert indice.total_representantes <= indice.total_eventos

    def test_repr_informativo(self, indice: IndiceSimilaridade) -> None:
        assert "vetores distintos" in repr(indice)


class TestConsulta:
    def test_aceita_o_json_do_enunciado(self, indice: IndiceSimilaridade) -> None:
        """As colunas redundantes presentes no JSON são simplesmente ignoradas."""
        contexto = indice.consultar(EVENTO_DO_ENUNCIADO)
        assert contexto.vizinhos
        assert contexto.condicao_informada == "cocked_rotor"
        assert contexto.tipo_condicao_informada == "defeito"
        assert contexto.rotulo_bruto == "cocked_rotor_2"

    def test_rejeita_evento_incompleto(self, indice: IndiceSimilaridade) -> None:
        incompleto = {k: v for k, v in EVENTO_DO_ENUNCIADO.items() if k != "temperature_c"}
        with pytest.raises(ValueError, match="temperature_c"):
            indice.consultar(incompleto)

    def test_respeita_o_numero_de_vizinhos(self, indice: IndiceSimilaridade) -> None:
        assert len(indice.consultar(EVENTO_DO_ENUNCIADO, vizinhos=3).vizinhos) == 3

    def test_vizinhos_ordenados_por_similaridade(self, indice: IndiceSimilaridade) -> None:
        similaridades = [v.similaridade for v in indice.consultar(EVENTO_DO_ENUNCIADO).vizinhos]
        assert similaridades == sorted(similaridades, reverse=True)

    def test_evento_do_historico_nao_e_seu_proprio_vizinho(
        self, eventos: pd.DataFrame, indice: IndiceSimilaridade
    ) -> None:
        registro = eventos.iloc[0]
        evento = {a: registro[a] for a in ATRIBUTOS} | {
            "id": int(registro["id"]),
            "fault": registro["fault"],
        }
        ids = {v.id for v in indice.consultar(evento).vizinhos}
        assert int(registro["id"]) not in ids

        ids_com_proprio = {
            v.id for v in indice.consultar(evento, excluir_proprio=False).vizinhos
        }
        assert int(registro["id"]) in ids_com_proprio


class TestBuscaGlobal:
    """ADR-008: a busca não filtra pelo rótulo informado."""

    def test_vizinhanca_pode_cruzar_familias(self, indice: IndiceSimilaridade) -> None:
        """A vizinhança de um defeito costuma incluir famílias distintas — evidência
        direta de que a assinatura vibratória não as separa (ADR-003)."""
        contexto = indice.consultar(EVENTO_DO_ENUNCIADO, vizinhos=25)
        assert len({v.condicao for v in contexto.vizinhos}) > 1

    def test_cada_vizinho_declara_sua_condicao(self, indice: IndiceSimilaridade) -> None:
        for vizinho in indice.consultar(EVENTO_DO_ENUNCIADO).vizinhos:
            assert vizinho.condicao
            assert vizinho.tipo_condicao in {"defeito", "estado", "desconhecido"}


class TestContextoExigidoPeloEnunciado:
    """Quantidade de eventos similares, distribuição no tempo, frequência e contexto
    operacional são saídas exigidas explicitamente."""

    @pytest.fixture(scope="class")
    def contexto(self, indice: IndiceSimilaridade):
        return indice.consultar(EVENTO_DO_ENUNCIADO)

    def test_quantidade_de_ocorrencias(self, contexto) -> None:
        assert contexto.ocorrencias
        assert contexto.total_ocorrencias_similares > 0
        assert all(o.ocorrencias_historicas > 0 for o in contexto.ocorrencias)

    def test_contagem_usa_o_historico_e_nao_os_vizinhos(self, contexto) -> None:
        """A contagem reportada é a frequência operacional real, muito maior que k."""
        for ocorrencia in contexto.ocorrencias:
            assert ocorrencia.ocorrencias_historicas >= ocorrencia.vizinhos

    def test_distribuicao_temporal(self, contexto) -> None:
        assert isinstance(contexto.distribuicao_temporal, pd.Series)
        assert len(contexto.distribuicao_temporal) > 0
        assert contexto.distribuicao_temporal.sum() > 0

    def test_frequencia_de_ocorrencia(self, contexto) -> None:
        for ocorrencia in contexto.ocorrencias:
            assert ocorrencia.frequencia_diaria > 0
            assert ocorrencia.primeira <= ocorrencia.ultima
            assert ocorrencia.dias_com_registro >= 1

    def test_contexto_operacional(self, contexto) -> None:
        assert contexto.contexto_operacional["rpm_predominante"] >= 0
        assert 0 < contexto.contexto_operacional["similaridade_media"] <= 1

    def test_ocorrencias_ordenadas_por_relevancia(self, contexto) -> None:
        contagens = [o.vizinhos for o in contexto.ocorrencias]
        assert contagens == sorted(contagens, reverse=True)


class TestSaturacaoDeCurtose:
    def test_leitura_saturada_nao_domina_a_distancia(self, indice: IndiceSimilaridade) -> None:
        """65,535 é o teto do registrador uint16. Censurado, não deve gerar vizinhança
        artificial entre eventos cujo único traço comum é ter estourado o sensor."""
        saturado = EVENTO_DO_ENUNCIADO | {"z_kurtosis": 65.535}
        contexto = indice.consultar(saturado)
        assert contexto.vizinhos
        assert all(v.similaridade > 0 for v in contexto.vizinhos)
