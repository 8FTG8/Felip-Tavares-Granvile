"""Contratos de entrada e saída da API (ADR-002).

O esquema de entrada reproduz o JSON descrito no enunciado, incluindo as colunas
redundantes que a solução ignora (ADR-007): o produtor do evento é o banco corporativo da
empresa, e exigir que ele altere o formato para acomodar uma decisão interna nossa seria
inverter a relação. Campos desconhecidos são aceitos e descartados.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.ingestion.eventos import ATRIBUTOS


class EventoSensor(BaseModel):
    """Leitura de sensor de vibração, no formato emitido pelo banco corporativo."""

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "id": 114387,
                "created_at": "2026-06-01 21:32:53.911176+00:00",
                "z_rms_velocity_mm_s": 1.517,
                "x_rms_velocity_mm_s": 2.0,
                "temperature_c": 24.69,
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
                "z_high_freq_rms_accel_g": 0.129,
                "x_high_freq_rms_accel_g": 0.147,
                "fault": "cocked_rotor_2",
                "rpm": 1000.0,
            }
        },
    )

    id: int | None = Field(default=None, description="Identificador do registro de origem")
    created_at: datetime | None = Field(default=None, description="Instante da leitura")
    fault: str | None = Field(
        default=None, description="Condição anotada manualmente pelo operador"
    )

    z_rms_velocity_mm_s: float
    x_rms_velocity_mm_s: float
    z_peak_acceleration_g: float
    x_peak_acceleration_g: float
    z_rms_acceleration_g: float
    x_rms_acceleration_g: float
    z_high_freq_rms_accel_g: float
    x_high_freq_rms_accel_g: float
    z_peak_vel_comp_freq_hz: float
    x_peak_vel_comp_freq_hz: float
    z_kurtosis: float
    x_kurtosis: float
    z_crest_factor: float
    x_crest_factor: float
    temperature_c: float
    rpm: float

    def atributos(self) -> dict[str, float]:
        """Somente os 16 atributos usados pela busca por similaridade (ADR-007)."""
        return {nome: getattr(self, nome) for nome in ATRIBUTOS}

    def para_consulta(self) -> dict:
        return self.atributos() | {"id": self.id, "fault": self.fault}


class PerguntaOpcional(BaseModel):
    """Consulta livre do técnico sobre o evento, quando houver."""

    pergunta: str | None = Field(
        default=None,
        max_length=500,
        description="Se ausente, usa-se uma consulta derivada da condição do evento",
    )


class OcorrenciaSimilar(BaseModel):
    """Uma ocorrência histórica semelhante ao evento analisado."""

    id: int
    created_at: datetime
    condicao: str
    tipo_condicao: str
    rotulo_bruto: str
    rpm: float
    similaridade: float
    leituras_identicas: int


class ResumoCondicao(BaseModel):
    """Contexto histórico de uma condição presente na vizinhança."""

    condicao: str
    tipo_condicao: str
    vizinhos: int
    ocorrencias_historicas: int
    primeira: datetime
    ultima: datetime
    dias_com_registro: int
    frequencia_diaria: float


class ContextoHistorico(BaseModel):
    """Resposta da busca por similaridade — o que o enunciado pede explicitamente."""

    total_ocorrencias_similares: int
    ocorrencias_por_condicao: list[ResumoCondicao]
    vizinhos: list[OcorrenciaSimilar]
    distribuicao_temporal: dict[str, int] = Field(
        description="Eventos por dia, para as condições presentes na vizinhança"
    )
    contexto_operacional: dict[str, float]


class Fonte(BaseModel):
    """Trecho de procedimento que fundamenta a recomendação."""

    documento: str
    numero_secao: int
    titulo_secao: str
    citacao: str
    relevancia: float
    origem: str


class AnaliseEvento(BaseModel):
    """Resposta completa da análise de um evento."""

    condicao: str = Field(description="Forma canônica da condição informada")
    tipo_condicao: str = Field(description="defeito, estado ou desconhecido")
    rotulo_bruto: str = Field(description="Rótulo exatamente como anotado pelo operador")
    caminho: str = Field(description="estado, sem_documento ou prescricao")
    motivo_recusa: str | None = None
    documento: str | None = None
    recomendacao: str
    gerada_por_llm: bool
    modelo: str | None = None
    fontes: list[Fonte] = Field(default_factory=list)
    contexto: ContextoHistorico | None = None
