/**
 * Ponte entre o design system e o que precisa de valores em JavaScript.
 *
 * Nem tudo consome estilo por classe. O Recharts recebe tamanho, espessura, altura e
 * margem como **números**; uma animação escalonada precisa do atraso em
 * milissegundos. É o ponto onde valores crus mais facilmente voltam a aparecer, e
 * onde reapareceriam sem que o verificador de tokens percebesse, porque
 * `barSize={14}` não é sintaxe de CSS.
 *
 * A solução é ler os próprios tokens do documento em vez de repeti-los aqui. Custa
 * uma leitura de estilo computado por token e por sessão, e elimina a possibilidade
 * de a escala do CSS e a dos gráficos divergirem — que foi exatamente o que
 * aconteceu antes, com eixos em 10px e 11px que não correspondiam a degrau algum.
 *
 * Este é o único arquivo autorizado a passar número a uma propriedade de estilo. O
 * verificador reprova qualquer outro.
 */

/**
 * Valor numérico de um token, na unidade em que foi declarado — pixels para medidas,
 * milissegundos para tempos. `rem` é convertido para pixels, porque é isso que o
 * Recharts espera.
 *
 * A leitura é preguiçosa e memoizada: no momento em que um módulo é avaliado a folha
 * de estilo pode ainda não estar aplicada, e um zero silencioso produziria gráficos
 * sem rótulo. Consultada na primeira renderização, ela já está.
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

  // Um token ausente é erro de programação, não condição de operação: falhar em
  // silêncio deixaria o gráfico ilegível sem explicar por quê.
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
 * Opacidade do preenchimento de área, do topo à base.
 *
 * Um degradê quase até zero, e não uma cor chapada: área sólida sob a linha compete
 * com as barras dos outros cartões pelo mesmo peso visual.
 */
export const AREA = { topo: 0.22, base: 0.02 } as const;

/**
 * Margens dos gráficos.
 *
 * Os valores negativos à esquerda não são folga: compensam a largura que o Recharts
 * reserva ao eixo Y mesmo quando os rótulos são curtos, e sem eles o gráfico fica
 * deslocado dentro do cartão. Ficam nomeados aqui porque, escritos no local, cada
 * página negociaria o seu e o alinhamento entre cartões vizinhos se perderia.
 */
export const MARGEM = {
  /** Série contínua com eixo Y de valores curtos. */
  serie: { left: -18, right: 6, top: 6 },
  /** Barras horizontais, com espaço à direita para o rótulo do valor. */
  categorias: { left: 8, right: 48 },
  /** Gráfico secundário, dentro de coluna estreita. */
  compacto: { left: -26, right: 4, top: 4 },
} as const;

/* ── Movimento ───────────────────────────────────────────────────────────────── */

/**
 * Atrasos dos três pontos do indicador de digitação.
 *
 * Derivados de um único token: escritos como `[0, 150, 300]`, eram três números
 * crus cuja relação — cada ponto atrasa um passo a mais que o anterior — ficava
 * implícita e se perdia ao primeiro ajuste.
 */
export const atrasosDigitacao = () => {
  const passo = medida("--passo-digitacao");
  return [0, passo, passo * 2];
};
