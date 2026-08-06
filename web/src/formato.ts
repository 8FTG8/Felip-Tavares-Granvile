/** Formatação de números para leitura em português. */

export const numero = (valor: number) => valor.toLocaleString("pt-BR");

/** Percentual para leitura, com vírgula decimal. */
export const percentual = (valor: number, casas = 1) =>
  `${(valor * 100).toFixed(casas).replace(".", ",")}%`;

/**
 * Percentual para uso em CSS, com ponto decimal. `width: "80,4%"` não é CSS válido e o
 * navegador o descarta em silêncio, deixando a barra sem preenchimento.
 */
export const percentualCss = (valor: number) => `${(valor * 100).toFixed(1)}%`;
