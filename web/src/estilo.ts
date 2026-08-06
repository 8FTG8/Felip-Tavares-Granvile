/**
 * Ponte entre o design system e o que precisa de valores em JavaScript.
 *
 * O Recharts recebe tamanho, espessura, altura e margem como números, e uma animação
 * escalonada precisa do atraso em milissegundos — casos que escapam ao verificador de
 * tokens, porque `barSize={14}` não é sintaxe de CSS. Em vez de repetir os valores,
 * este módulo lê os tokens do documento, o que impede a escala do CSS e a dos gráficos
 * de divergirem.
 *
 * É o único arquivo autorizado a passar número a uma propriedade de estilo.
 */

/**
 * Valor numérico de um token, na unidade declarada — pixels para medidas,
 * milissegundos para tempos. `rem` é convertido para pixels, que é o que o Recharts
 * espera.
 *
 * A leitura é preguiçosa e memoizada: no momento em que o módulo é avaliado a folha de
 * estilo pode ainda não estar aplicada, e um zero silencioso produziria gráficos sem
 * rótulo.
 */
const cache = new Map<string, number>();

export function medida(token: string): number {
  const guardado = cache.get(token);
  if (guardado !== undefined) return guardado;

  const raiz = document.documentElement;
  const estilo = getComputedStyle(raiz);
  const bruto = estilo.getPropertyValue(token).trim();
  const base = parseFloat(estilo.fontSize) || 16;
  const valor = bruto.endsWith("rem") ? parseFloat(bruto) * base : parseFloat(bruto);

  // Token ausente é erro de programação, e falhar em silêncio deixaria o gráfico
  // ilegível sem explicar por quê.
  if (!Number.isFinite(valor)) throw new Error(`Token ausente ou não numérico: ${token}`);

  cache.set(token, valor);
  return valor;
}

/* ── Cor ─────────────────────────────────────────────────────────────────────── */

/** Cores citáveis em propriedades que não aceitam classe utilitária. */
export const COR = {
  acento: "var(--color-acento)",
  sucesso: "var(--color-sucesso)",
  alerta: "var(--color-alerta)",
  tintaSecundaria: "var(--color-tinta-secundaria)",
  tintaSuave: "var(--color-tinta-suave)",
  borda: "var(--color-borda)",
  grade: "var(--color-grade)",
} as const;

/* ── Medidas de gráfico ──────────────────────────────────────────────────────── */

/** Cursor de destaque sob a barra apontada. */
export const CURSOR = { fill: COR.grade } as const;

/** Raio do topo das barras verticais e da ponta das horizontais. */
export const raioBarra = () => medida("--radius-sutil");

/** Espessura da barra no gráfico de cobertura, onde há doze faixas empilhadas. */
export const espessuraBarra = () => medida("--espessura-barra");

/** Espessura da linha da série temporal. */
export const espessuraLinha = () => medida("--espessura-linha");

/** Largura reservada aos nomes de condição no eixo categórico. */
export const larguraEixoCategoria = () => medida("--largura-eixo-categoria");

/** Distância mínima entre marcações de data, para que não colidam. */
export const espacoMarcacao = () => medida("--espaco-marcacao");

/** Marcação de eixo: um degrau da escala, na tinta mais recuada que ainda passa. */
export const marcacao = (recuada = true) => ({
  fontSize: medida("--text-nota"),
  fill: recuada ? COR.tintaSuave : COR.tintaSecundaria,
});

/**
 * Opacidade do preenchimento de área, do topo à base. Degradê quase até zero: área
 * sólida sob a linha competiria com as barras dos outros cartões.
 */
export const AREA = { topo: 0.22, base: 0.02 } as const;

/**
 * Margens dos gráficos, nomeadas aqui para que o alinhamento entre cartões vizinhos
 * não dependa de cada página negociar a sua.
 *
 * `serie` não usa margem negativa para recuperar os 60px que o Recharts reserva ao
 * eixo Y: a margem cortava o primeiro caractere de rótulos de cinco dígitos. A largura
 * do eixo é declarada por `larguraEixoValor`.
 */
export const MARGEM = {
  /** Série contínua, com o eixo Y dimensionado pelo maior valor. */
  serie: { left: 0, right: 6, top: 6 },
  /** Barras horizontais, com espaço à direita para o rótulo do valor. */
  categorias: { left: 8, right: 48 },
  /** Gráfico secundário, dentro de coluna estreita. */
  compacto: { left: -26, right: 4, top: 4 },
} as const;

/**
 * Espaço que o eixo Y ocupa, para descontar da área de desenho.
 *
 * É estimativa, e só serve para decidir se um rótulo de faixa cabe — o eixo em si usa
 * `width="auto"`, e quem mede os rótulos que ele de fato renderizou é o Recharts.
 * Errar aqui esconde ou mostra um rótulo no limite, e nada além disso.
 */
export function larguraEixoValor(maximo: number): number {
  const rotulo = String(Math.round(maximo));
  return larguraTexto(rotulo, medida("--text-nota")) + medida("--espaco-rotulo-eixo");
}

/** Pixels disponíveis ao desenho de uma série: o cartão menos o eixo e as margens. */
export function larguraDesenho(larguraDoCartao: number, larguraDoEixo: number): number {
  const { left, right } = MARGEM.serie;
  return Math.max(0, larguraDoCartao - larguraDoEixo - left - right);
}

/**
 * Largura de um texto em pixels, medida num elemento fora de vista dentro do próprio
 * documento.
 *
 * A régua é um `<span>`, e não um `canvas`, porque `ctx.font` exige a abreviação de
 * fonte do CSS e ignora em silêncio o que não consegue interpretar — a pilha de
 * `--font-sans` não passa, e o contexto continua no padrão de 10px, devolvendo uma
 * largura pequena demais. Um elemento no documento herda a fonte que a página está
 * usando, seja qual for a que o navegador escolheu da pilha.
 */
let regua: HTMLSpanElement | null = null;

export function larguraTexto(texto: string, tamanho: number): number {
  if (!regua) {
    regua = document.createElement("span");
    regua.setAttribute("aria-hidden", "true");
    regua.style.cssText =
      "position:absolute;top:-9999px;left:-9999px;white-space:pre;visibility:hidden";
    document.body.appendChild(regua);
  }
  regua.style.fontSize = `${tamanho}px`;
  regua.textContent = texto;
  return regua.getBoundingClientRect().width;
}

/* ── Movimento ───────────────────────────────────────────────────────────────── */

/**
 * Atrasos dos três pontos do indicador de digitação, derivados de um passo único —
 * cada ponto atrasa um passo a mais que o anterior.
 */
export const atrasosDigitacao = () => {
  const passo = medida("--passo-digitacao");
  return [0, passo, passo * 2];
};
