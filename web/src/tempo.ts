/** Contagem de tempo decorrido, para esperas longas. */

import { useEffect, useState } from "react";

/**
 * Segundos decorridos desde que `ativo` passou a ser verdadeiro.
 *
 * A geração do modelo leva dezenas de segundos em estação sem GPU dedicada, e um
 * indicador pulsante não distingue "gerando há dois segundos" de "travado".
 */
export function useDecorrido(ativo: boolean): number {
  const [segundos, setSegundos] = useState(0);

  useEffect(() => {
    if (!ativo) {
      setSegundos(0);
      return;
    }
    const inicio = Date.now();
    // O relógio é lido a cada tique, em vez de incrementado: um contador acumulado
    // atrasa quando a aba fica em segundo plano, e o navegador estrangula os timers
    // justamente durante uma espera longa.
    const tique = setInterval(() => {
      setSegundos(Math.floor((Date.now() - inicio) / 1000));
    }, 1000);
    return () => clearInterval(tique);
  }, [ativo]);

  return segundos;
}
