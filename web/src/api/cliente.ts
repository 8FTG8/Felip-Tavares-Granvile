/**
 * Cliente HTTP da API de manutenção prescritiva (ADR-002).
 *
 * A interface não reimplementa regra de domínio: usa os mesmos endpoints que um
 * supervisório ou um CMMS usaria.
 */

import type {
  AnaliseEvento,
  CoberturaDocumental,
  DocumentoRegistrado,
  EstadoSistema,
  EventoSensor,
  PainelHistorico,
  RoteamentoFluxo,
} from "./tipos";

// Não há método de chat síncrono: em estação sem GPU dedicada a geração leva dezenas de
// segundos, e a conversa usa exclusivamente o fluxo.

const BASE = import.meta.env.VITE_API_URL ?? "/api";

/** A API não respondeu, ou respondeu erro em endpoint que deveria existir. */
export class ApiIndisponivel extends Error {}

/** A API recusou a requisição por conteúdo inválido — mensagem exibível ao usuário. */
export class RequisicaoRecusada extends Error {}

/**
 * A API respondeu, mas o serviço de modelos não pôde atender. Distinta de
 * `ApiIndisponivel` porque a ação corretiva é subir o Ollama, não a API.
 */
export class ModeloIndisponivel extends Error {}

/**
 * Traduz uma resposta de erro na exceção correspondente — três situações com três ações
 * corretivas: 415/422 é o que foi enviado e merece a mensagem da API; 503 é o serviço de
 * modelos fora do ar; o resto é indisponibilidade da própria API.
 */
async function lancarErro(resposta: Response, caminho: string): Promise<never> {
  if (resposta.status === 415 || resposta.status === 422) {
    const corpo = await resposta.json().catch(() => null);
    throw new RequisicaoRecusada(detalhar(corpo) ?? "Requisição recusada pela API.");
  }
  if (resposta.status === 503) {
    const corpo = await resposta.json().catch(() => null);
    throw new ModeloIndisponivel(
      detalhar(corpo) ?? "O serviço de modelos não está respondendo.",
    );
  }
  throw new ApiIndisponivel(`${caminho} respondeu ${resposta.status}`);
}

async function requisitar<T>(caminho: string, opcoes?: RequestInit): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(`${BASE}${caminho}`, opcoes);
  } catch (erro) {
    throw new ApiIndisponivel(String(erro));
  }
  if (!resposta.ok) await lancarErro(resposta, caminho);
  return resposta.json() as Promise<T>;
}

/** Extrai a mensagem legível do corpo de erro, seja texto ou lista de campos do Pydantic. */
function detalhar(corpo: unknown): string | null {
  if (!corpo || typeof corpo !== "object") return null;
  const detalhe = (corpo as { detail?: unknown }).detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe)) {
    const mensagem = (detalhe[0] as { msg?: string })?.msg;
    const campos = detalhe
      .map((item) => (item as { loc?: unknown[] }).loc?.slice(-1)[0])
      .filter(Boolean)
      .join(", ");
    if (campos && mensagem) return `${mensagem} (${campos})`;
    if (campos) return `Campos inválidos ou ausentes: ${campos}.`;
  }
  return null;
}

export const api = {
  sistema: (sinal?: AbortSignal) => requisitar<EstadoSistema>("/sistema", { signal: sinal }),

  estatisticas: (sinal?: AbortSignal) =>
    requisitar<PainelHistorico>("/estatisticas", { signal: sinal }),

  cobertura: (sinal?: AbortSignal) =>
    requisitar<CoberturaDocumental[]>("/documentos/cobertura", { signal: sinal }),

  analisar: (evento: EventoSensor, pergunta?: string, sinal?: AbortSignal) => {
    const busca = pergunta ? `?pergunta=${encodeURIComponent(pergunta)}` : "";
    return requisitar<AnaliseEvento>(`/eventos/analisar${busca}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(evento),
      signal: sinal,
    });
  },

  cadastrarDocumento: (condicao: string, arquivo: File) => {
    const dados = new FormData();
    dados.append("condicao", condicao);
    dados.append("arquivo", arquivo);
    return requisitar<DocumentoRegistrado>("/documentos", { method: "POST", body: dados });
  },

  /**
   * Conversa com a resposta transmitida em partes.
   *
   * Roteamento e citações chegam nos cabeçalhos, antes do primeiro token, o que evita uma
   * segunda chamada só para obter as fontes. Cabeçalhos HTTP são limitados a latin-1 e as
   * citações têm acentuação, daí a decodificação percentual.
   *
   * O sinal de cancelamento é necessário na prática: a geração leva dezenas de segundos, e
   * sair da tela deixaria a leitura do fluxo escrevendo num componente desmontado.
   */
  conversarEmFluxo: async (
    pergunta: string,
    condicao: string | null,
    historico: TurnoConversa[],
    aoReceber: (parcial: string) => void,
    sinal?: AbortSignal,
  ): Promise<RoteamentoFluxo> => {
    let resposta: Response;
    try {
      resposta = await fetch(`${BASE}/chat/fluxo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pergunta, condicao, historico }),
        signal: sinal,
      });
    } catch (erro) {
      throw new ApiIndisponivel(String(erro));
    }

    if (!resposta.ok) await lancarErro(resposta, "/chat/fluxo");
    if (!resposta.body) throw new ApiIndisponivel("/chat/fluxo não devolveu corpo");

    let fontes: string[] = [];
    try {
      fontes = JSON.parse(decodeURIComponent(resposta.headers.get("x-fontes") ?? "[]"));
    } catch {
      // Cabeçalho malformado não invalida o texto: segue sem a lista de citações.
      fontes = [];
    }

    const roteamento: RoteamentoFluxo = {
      caminho: (resposta.headers.get("x-caminho") ?? "") as RoteamentoFluxo["caminho"],
      condicao: resposta.headers.get("x-condicao") ?? "",
      documento: resposta.headers.get("x-documento") ?? "",
      fontes,
    };

    const leitor = resposta.body.getReader();
    const decodificador = new TextDecoder();
    let acumulado = "";
    for (;;) {
      const { done, value } = await leitor.read();
      if (done) break;
      acumulado += decodificador.decode(value, { stream: true });
      aoReceber(acumulado);
    }
    // Esvazia o decodificador: um caractere multibyte partido entre dois blocos só é
    // resolvido nesta chamada final.
    acumulado += decodificador.decode();
    aoReceber(acumulado);

    return roteamento;
  },
};

export interface TurnoConversa {
  papel: "usuario" | "assistente";
  conteudo: string;
}
