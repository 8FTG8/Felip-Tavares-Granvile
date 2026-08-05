/**
 * Vocabulário das condições, em português.
 *
 * As 17 formas canônicas produzidas pela normalização (`src/ingestion/rotulos.py`) são
 * identificadores de banco: `rolamento_combination`, `cocked_rotor`, `eccentric_rotor`.
 * Servem para indexar, comparar e citar — não para ler. Um técnico de manutenção não
 * reconhece nenhum deles, e a tela pedia justamente que ele escolhesse um numa lista de
 * doze.
 *
 * **O identificador nunca é escondido.** Ele aparece em toda parte como legenda
 * secundária, em monoespaçada: é o que chega no JSON do sensor, o que a API devolve e o
 * que aparece na citação. Trocar um pelo outro quebraria a rastreabilidade que o produto
 * inteiro existe para oferecer; o nome em português vem *junto*, não no lugar.
 *
 * A tradução segue a terminologia usual de análise de vibração em máquinas rotativas.
 * Dois pontos mereceram cuidado:
 *
 * - `cocked_rotor` **não** é "rotor desalinhado": `desalinhado` já é outra condição
 *   distinta neste mesmo conjunto, e usar a palavra nas duas as tornaria indistinguíveis
 *   exatamente onde a demonstração mostra que a assinatura vibratória não as separa.
 *   Ficou "Rotor inclinado no eixo", que é o defeito de montagem que o termo descreve.
 * - As quatro famílias de rolamento compartilham prefixo para ordenarem juntas e para
 *   deixar visível que são o mesmo componente com origens diferentes — o que também
 *   explica por que as quatro apontam para o mesmo documento.
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
 * Nome legível de uma condição.
 *
 * Devolve o próprio identificador quando não há tradução — o caso de uma condição
 * cadastrada em operação, depois que este arquivo foi escrito. Exibir o identificador
 * cru é pior que exibir um nome, e muito melhor que exibir nada.
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
