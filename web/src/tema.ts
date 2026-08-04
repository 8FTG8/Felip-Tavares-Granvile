/**
 * Escolha do tema claro ou escuro.
 *
 * A preferência do sistema é o ponto de partida, não a regra: uma vez que o usuário
 * escolhe, a escolha vence e persiste. Numa demonstração isso importa — a sala pode estar
 * escura enquanto o sistema operacional está em modo claro, ou o contrário.
 */

import { useEffect, useState } from "react";

export type Tema = "claro" | "escuro";

const CHAVE = "tema";

function temaInicial(): Tema {
  const salvo = localStorage.getItem(CHAVE);
  if (salvo === "claro" || salvo === "escuro") return salvo;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "escuro" : "claro";
}

export function useTema() {
  const [tema, definirTema] = useState<Tema>(temaInicial);

  useEffect(() => {
    document.documentElement.dataset.tema = tema;
    localStorage.setItem(CHAVE, tema);
  }, [tema]);

  return {
    tema,
    alternar: () => definirTema((atual) => (atual === "claro" ? "escuro" : "claro")),
  };
}
