/**
 * Moldura de gráfico com altura vinda de token: nenhuma página escreve altura em
 * pixels, só o nome de um degrau — baixo, médio ou alto.
 *
 * Cores, medidas e margens ficam em `src/estilo.ts`.
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
