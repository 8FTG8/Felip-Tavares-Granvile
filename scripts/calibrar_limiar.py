"""Calibra empiricamente o limiar da segunda barreira do guardrail (ADR-010).

A primeira barreira — o mapa defeito → documento — é determinística e não tem parâmetro
a ajustar. A segunda cobre um caso diferente: existe documento para o defeito, mas
nenhuma seção dele responde à pergunta feita. Esse julgamento precisa de um corte
numérico, e um corte arbitrário é indefensável.

O procedimento monta dois conjuntos de perguntas dirigidas a um documento específico:

* **pertinentes** — perguntas que o documento de fato responde;
* **impertinentes** — perguntas sobre assuntos ausentes daquele documento, formuladas no
  mesmo registro técnico, para que a diferença medida venha do conteúdo e não do estilo.

O limiar é escolhido no ponto que melhor separa as duas distribuições. O resultado, com
as distribuições completas, é impresso para registro no notebook de análise.

Uso::

    python scripts/calibrar_limiar.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from src.rag.indice_documental import IndiceDocumental
from src.rag.mapeamento import MAPA


@dataclass(frozen=True)
class Caso:
    documento: str
    pergunta: str
    pertinente: bool


#: Perguntas que o documento roteado responde. Uma por seção prescritiva relevante.
PERTINENTES = [
    ("Doc1", "como corrigir um defeito na pista interna do rolamento"),
    ("Doc1", "qual o procedimento para substituir um rolamento danificado"),
    ("Doc1", "como identificar falta de lubrificação no rolamento"),
    ("Doc1", "quais as frequências características de defeito em rolamentos"),
    ("Doc2", "como corrigir o desalinhamento vertical do motor"),
    ("Doc2", "o que é pé manco e como corrigir"),
    ("Doc2", "quais os critérios de aceitação após o alinhamento"),
    ("Doc3", "como fazer o balanceamento dinâmico do rotor"),
    ("Doc3", "como calcular a massa de correção do desbalanceamento"),
    ("Doc3", "quais os sintomas de desbalanceamento em máquina rotativa"),
    ("Doc4", "como ajustar a tensão de uma correia frouxa"),
    ("Doc4", "qual o procedimento de substituição da correia"),
    ("Doc5", "como corrigir a excentricidade da polia"),
    ("Doc5", "como verificar o desgaste das ranhuras da polia"),
    ("Doc6", "como corrigir um rotor inclinado montado incorretamente"),
    ("Doc6", "como diferenciar cocked rotor de desbalanceamento"),
]

#: Perguntas técnicas legítimas cujo assunto não está no documento roteado. É o caso que
#: a segunda barreira precisa capturar: documento existe, resposta não.
IMPERTINENTES = [
    ("Doc1", "como corrigir a falta de fase na alimentação trifásica do motor"),
    ("Doc1", "como dimensionar o inversor de frequência do acionamento"),
    ("Doc1", "qual o procedimento de limpeza química do trocador de calor"),
    ("Doc2", "como calcular a perda de carga na tubulação de recalque"),
    ("Doc2", "como programar o CLP para intertravamento de segurança"),
    ("Doc3", "como fazer a manutenção do sistema hidráulico da prensa"),
    ("Doc3", "qual a norma aplicável para aterramento elétrico do painel"),
    ("Doc4", "como ajustar os parâmetros de soldagem MIG",),
    ("Doc4", "como interpretar o laudo de análise de óleo lubrificante"),
    ("Doc5", "como calibrar o transmissor de pressão diferencial"),
    ("Doc5", "qual o procedimento de teste hidrostático do vaso de pressão"),
    ("Doc6", "como configurar a rede Profibus do supervisório"),
    ("Doc6", "como corrigir a cavitação da bomba centrífuga"),
    ("Doc6", "qual o intervalo de troca do filtro de ar comprimido"),
]


def medir(indice: IndiceDocumental) -> list[tuple[Caso, float]]:
    casos = [Caso(d, p, True) for d, p in PERTINENTES] + [
        Caso(d, p, False) for d, p in IMPERTINENTES
    ]
    medidas: list[tuple[Caso, float]] = []
    for caso in casos:
        recuperados = indice.buscar(caso.pergunta, documento=caso.documento, trechos=4)
        melhor = max((t.relevancia for t in recuperados), default=0.0)
        medidas.append((caso, melhor))
    return medidas


def escolher_limiar(medidas: list[tuple[Caso, float]]) -> tuple[float, dict]:
    """Escolhe o corte que melhor separa os dois conjuntos, com margem máxima.

    Os candidatos são os **pontos médios** entre valores medidos consecutivos, e não os
    valores em si: um limiar posto exatamente sobre uma medição fica à mercê da precisão
    de ponto flutuante, e a comparação ``>=`` passa a depender do último dígito.

    Entre cortes de desempenho equivalente, escolhe-se o de maior margem — o mais
    distante de qualquer medição. Um limiar colado no menor valor pertinente separaria
    igualmente bem *neste* conjunto de calibração e quebraria à primeira consulta real
    ligeiramente mais fraca.
    """
    pertinentes = [r for caso, r in medidas if caso.pertinente]
    impertinentes = [r for caso, r in medidas if not caso.pertinente]

    valores = sorted({r for _, r in medidas})
    candidatos = [(a + b) / 2 for a, b in zip(valores, valores[1:])]
    if not candidatos:
        return 0.0, {}

    melhor_limiar, melhor_escore, melhor_margem, melhor_detalhe = 0.0, -1.0, -1.0, {}

    for limiar in candidatos:
        aceitos = sum(1 for r in pertinentes if r >= limiar)
        rejeitados = sum(1 for r in impertinentes if r < limiar)
        escore = aceitos / len(pertinentes) + rejeitados / len(impertinentes)
        margem = min(abs(limiar - v) for v in valores)

        if (escore, margem) > (melhor_escore, melhor_margem):
            melhor_limiar, melhor_escore, melhor_margem = limiar, escore, margem
            melhor_detalhe = {
                "pertinentes_aceitos": aceitos,
                "pertinentes_total": len(pertinentes),
                "impertinentes_rejeitados": rejeitados,
                "impertinentes_total": len(impertinentes),
                "margem": margem,
            }

    return melhor_limiar, melhor_detalhe


def main() -> int:
    faltando = {d for d in MAPA.values() if d} - {d for d, _ in PERTINENTES}
    if faltando:
        print(f"aviso: documentos sem caso pertinente: {sorted(faltando)}")

    indice = IndiceDocumental()
    if indice.garantir_indexado() == 0:
        print("base documental vazia — nada a calibrar")
        return 1

    medidas = medir(indice)
    pertinentes = sorted((r for c, r in medidas if c.pertinente))
    impertinentes = sorted((r for c, r in medidas if not c.pertinente))

    print(f"pertinentes   n={len(pertinentes):2}  "
          f"min={pertinentes[0]:.4f}  mediana={pertinentes[len(pertinentes)//2]:.4f}  "
          f"max={pertinentes[-1]:.4f}")
    print(f"impertinentes n={len(impertinentes):2}  "
          f"min={impertinentes[0]:.4f}  mediana={impertinentes[len(impertinentes)//2]:.4f}  "
          f"max={impertinentes[-1]:.4f}")
    print(f"\nsobreposição: {'SIM' if impertinentes[-1] >= pertinentes[0] else 'NÃO'}")

    limiar, detalhe = escolher_limiar(medidas)
    print(f"\nlimiar escolhido: {limiar:.4f}")
    print(f"  pertinentes aceitos ....... {detalhe['pertinentes_aceitos']}/{detalhe['pertinentes_total']}")
    print(f"  impertinentes rejeitados .. {detalhe['impertinentes_rejeitados']}/{detalhe['impertinentes_total']}")
    print(f"  margem ao caso mais proximo {detalhe['margem']:.4f}")

    print("\ndetalhe por caso:")
    for caso, relevancia in sorted(medidas, key=lambda m: -m[1]):
        marca = "+" if caso.pertinente else "-"
        decisao = "aceita" if relevancia >= limiar else "recusa"
        print(f"  {marca} {relevancia:.4f} {decisao:7} {caso.documento} | {caso.pergunta[:58]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
