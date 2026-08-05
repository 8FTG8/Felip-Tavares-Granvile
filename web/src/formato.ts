/** Formatação de números para leitura em português. */

export const numero = (valor: number) => valor.toLocaleString("pt-BR");

/** Percentual para leitura humana — com vírgula decimal, como se escreve em português. */
export const percentual = (valor: number, casas = 1) =>
  `${(valor * 100).toFixed(casas).replace(".", ",")}%`;

/**
 * Percentual para uso em CSS.
 *
 * Existe separado de :func:`percentual` porque a vírgula decimal do português produz
 * um valor que o navegador descarta silenciosamente: `width: "80,4%"` não é CSS
 * válido, e a barra simplesmente não preenche.
 */
export const percentualCss = (valor: number) => `${(valor * 100).toFixed(1)}%`;
