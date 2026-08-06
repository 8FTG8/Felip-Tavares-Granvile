/**
 * Vocabulário das condições, em português.
 *
 * As 17 formas canônicas da normalização (`src/ingestion/rotulos.py`) são
 * identificadores de banco — `rolamento_combination`, `cocked_rotor` —, próprios para
 * indexar e citar, não para ler.
 *
 * O identificador nunca é escondido: aparece junto, como legenda secundária em
 * monoespaçada, porque é o que chega no JSON do sensor, o que a API devolve e o que
 * consta da citação. O nome em português vem junto, não no lugar.
 *
 * Duas escolhas de tradução:
 *
 * - `cocked_rotor` é "Rotor inclinado no eixo", não "rotor desalinhado": `desalinhado`
 *   é outra condição do mesmo conjunto, e a assinatura vibratória não separa as duas.
 * - As quatro famílias de rolamento compartilham prefixo para ordenarem juntas; são o
 *   mesmo componente com origens diferentes, e apontam para o mesmo documento.
 */

/** Defeitos — as 12 famílias que podem receber prescrição. */
const DEFEITOS: Record<string, string> = {
  cocked_rotor: "Rotor inclinado no eixo",
  correia: "Defeito em correia",
  desalinhado: "Desalinhamento de eixos",
  desbalanceado: "Desbalanceamento do rotor",
  eccentric_rotor: "Rotor excêntrico",
  falta_fase: "Falta de fase",
  polia: "Defeito em polia",
  rolamento_ball: "Rolamento — esferas",
  rolamento_combination: "Rolamento — defeitos combinados",
  rolamento_inner: "Rolamento — pista interna",
  rolamento_outer: "Rolamento — pista externa",
  ventoinha: "Defeito em ventoinha",
};

/** Estados operacionais — não são falha, e por isso não recebem prescrição. */
const ESTADOS: Record<string, string> = {
  acelerando: "Em aceleração",
  baseline: "Linha de base",
  motor_desligado: "Motor desligado",
  normal: "Operação normal",
  teste: "Ensaio",
};

const NOMES: Record<string, string> = { ...DEFEITOS, ...ESTADOS };

/**
 * Nome legível de uma condição. Sem tradução, devolve o próprio identificador — o caso
 * de uma condição cadastrada em operação, depois que este arquivo foi escrito.
 */
export function nomeCondicao(condicao: string): string {
  return NOMES[condicao] ?? condicao;
}

/** Ordena por nome legível, que é o que a pessoa está lendo na tela. */
export function porNome(a: string, b: string): number {
  return nomeCondicao(a).localeCompare(nomeCondicao(b), "pt-BR");
}

/** As 12 famílias de defeito, na ordem em que serão lidas. */
export const DEFEITOS_ORDENADOS = Object.keys(DEFEITOS).sort(porNome);
