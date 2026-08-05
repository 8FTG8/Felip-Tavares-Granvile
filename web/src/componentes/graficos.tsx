/**
 * Moldura de gráfico com altura vinda de token.
 *
 * Existe para que nenhuma página escreva uma altura em pixels: ela passa a ser o
 * nome de um degrau — baixo, médio ou alto — e não um número negociado no local.
 *
 * As cores, medidas e margens que os gráficos consomem ficam em `src/estilo.ts`,
 * junto com a leitura dos tokens.
 */

import type { ReactNode } from "react";
import { ResponsiveContainer } from "recharts";
import { medida } from "../estilo";

export function Moldura({
  altura = "medio",
  children,
}: {
  altura?: "baixo" | "medio" | "alto";
  children: ReactNode;
}) {
  const tokens = {
    baixo: "--altura-grafico-baixo",
    medio: "--altura-grafico",
    alto: "--altura-grafico-alto",
  } as const;

  return (
    <ResponsiveContainer width="100%" height={medida(tokens[altura])}>
      {children as React.ReactElement}
    </ResponsiveContainer>
  );
}
