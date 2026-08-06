/**
 * Contratos da API de manutenção prescritiva.
 *
 * Espelham os esquemas Pydantic de `src/api/esquemas.py`. Escritos à mão, e não gerados
 * do OpenAPI: são poucos e estáveis, e o arquivo documenta o que a interface consome.
 */

/** Caminho de resposta escolhido pelo roteador, antes de qualquer geração de texto. */
export type Caminho = "prescricao" | "sem_documento" | "estado" | "sem_condicao";

export interface Fonte {
  documento: string;
  numero_secao: number;
  titulo_secao: string;
  citacao: string;
  relevancia: number;
  origem: "nativo" | "ocr";
}

export interface OcorrenciaSimilar {
  id: number;
  created_at: string;
  condicao: string;
  tipo_condicao: string;
  rotulo_bruto: string;
  rpm: number;
  similaridade: number;
  leituras_identicas: number;
}

export interface ResumoCondicao {
  condicao: string;
  tipo_condicao: string;
  vizinhos: number;
  ocorrencias_historicas: number;
  primeira: string;
  ultima: string;
  dias_com_registro: number;
  frequencia_diaria: number;
}

export interface ContextoHistorico {
  total_ocorrencias_similares: number;
  ocorrencias_por_condicao: ResumoCondicao[];
  vizinhos: OcorrenciaSimilar[];
  distribuicao_temporal: Record<string, number>;
  contexto_operacional: Record<string, number>;
}

export interface AnaliseEvento {
  condicao: string;
  tipo_condicao: string;
  rotulo_bruto: string;
  caminho: Caminho;
  motivo_recusa: string | null;
  documento: string | null;
  recomendacao: string;
  gerada_por_llm: boolean;
  modelo: string | null;
  fontes: Fonte[];
  contexto: ContextoHistorico | null;
}

export interface RespostaChat {
  resposta: string;
  caminho: Caminho;
  condicao: string | null;
  documento: string | null;
  motivo_recusa: string | null;
  gerada_por_llm: boolean;
  modelo: string | null;
  fontes: Fonte[];
}

export interface CoberturaDocumental {
  condicao: string;
  documentada: boolean;
  documento: string | null;
  cadastrado_em_operacao: boolean;
  justificativa: string;
}

export interface DocumentoRegistrado {
  condicao: string;
  documento: string;
  trechos: number;
  origem: "nativo" | "ocr";
  cadastrado_em: string;
  secoes: string[];
}

export interface CondicaoNoHistorico {
  condicao: string;
  tipo_condicao: string;
  eventos: number;
  proporcao: number;
  primeira: string;
  ultima: string;
  dias_com_registro: number;
  frequencia_diaria: number;
  rotulos_brutos: number;
  documentada: boolean;
  documento: string | null;
}

/** Trecho contíguo de dias em que um mesmo defeito domina os registros. */
export interface BlocoDeCampanha {
  condicao: string;
  primeiro_dia: string;
  ultimo_dia: string;
  dias: number;
  /** Fração média dos eventos do dia pertencentes à condição dominante. */
  dominancia: number;
}

export interface PainelHistorico {
  resumo: {
    total_eventos: number;
    total_defeitos: number;
    total_estados: number;
    familias_de_defeito: number;
    primeiro_evento: string;
    ultimo_evento: string;
    dias_com_registro: number;
    cobertura_documental: number;
  };
  condicoes: CondicaoNoHistorico[];
  eventos_por_dia: Record<string, number>;
  eventos_por_rpm: Record<string, number>;
  campanhas: BlocoDeCampanha[];
}

export interface EstadoSistema {
  modelo: string;
  modelo_disponivel: boolean;
  limiar_relevancia: number;
  trechos_indexados: number;
  eventos_indexados: number;
  familias_documentadas: number;
  familias_totais: number;
}

/**
 * Leitura de sensor, no formato emitido pelo banco corporativo.
 *
 * Os dezesseis atributos que o índice de similaridade consome aparecem nomeados, para
 * que um erro de digitação como `z_kurtosos` falhe na compilação e não na resposta da
 * API.
 *
 * Todos são opcionais: a validação de obrigatoriedade é da API (Pydantic), e duplicá-la
 * aqui criaria duas fontes de verdade. A assinatura de índice cobre as sete colunas
 * redundantes que o banco emite e a ingestão descarta.
 */
export interface EventoSensor {
  id?: number;
  created_at?: string;
  fault?: string;

  rpm?: number;
  temperature_c?: number;

  z_rms_velocity_mm_s?: number;
  x_rms_velocity_mm_s?: number;
  z_peak_acceleration_g?: number;
  x_peak_acceleration_g?: number;
  z_peak_vel_comp_freq_hz?: number;
  x_peak_vel_comp_freq_hz?: number;
  z_rms_acceleration_g?: number;
  x_rms_acceleration_g?: number;
  z_kurtosis?: number;
  x_kurtosis?: number;
  z_crest_factor?: number;
  x_crest_factor?: number;
  z_high_freq_rms_accel_g?: number;
  x_high_freq_rms_accel_g?: number;

  /** Colunas redundantes do banco corporativo, aceitas e descartadas pela ingestão. */
  [coluna: string]: number | string | undefined;
}

/** Roteamento transmitido nos cabeçalhos da resposta em fluxo. */
export interface RoteamentoFluxo {
  caminho: Caminho | "";
  condicao: string;
  documento: string;
  fontes: string[];
}
