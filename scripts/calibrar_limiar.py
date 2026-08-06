"""Calibra empiricamente o limiar da segunda barreira do guardrail (ADR-010).

A primeira barreira — o mapa defeito → documento — é determinística e não tem parâmetro
a ajustar. A segunda cobre um caso diferente: existe documento para o defeito, mas
nenhuma seção dele responde à pergunta feita. Esse julgamento precisa de um corte
numérico, e um corte arbitrário é indefensável.

O procedimento monta dois conjuntos de perguntas dirigidas a um documento específico:

* **pertinentes** — perguntas que o documento de fato responde;
* **impertinentes** — perguntas sobre assuntos ausentes daquele documento, formuladas no
  mesmo registro técnico, para que a diferença medida venha do conteúdo e não do estilo.

Cada conjunto tem perguntas longas e curtas. A distinção não é decorativa: a primeira
calibração usou apenas perguntas longas e bem formuladas, e o limiar resultante recusou
perguntas legítimas de chat — "o eixo pode estar empenado?" — porque o comprimento do
texto domina a similaridade de cosseno. Um conjunto de calibração que não representa o uso
real produz um número que não descreve o sistema.

As consultas passam por :func:`montar_consulta`, exatamente como no roteador. Medir uma
coisa e produzir outra invalidaria o corte.

Uso::

    python scripts/calibrar_limiar.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from src.rag.indice_documental import IndiceDocumental
from src.rag.mapeamento import MAPA
from src.rag.roteador import TRECHOS_PADRAO, montar_consulta


@dataclass(frozen=True)
class Caso:
    documento: str
    condicao: str
    pergunta: str
    pertinente: bool
    curta: bool = False


#: Perguntas completas que o documento roteado responde.
PERTINENTES = [
    ("Doc1", "rolamento_inner", "como corrigir um defeito na pista interna do rolamento"),
    ("Doc1", "rolamento_inner", "qual o procedimento para substituir um rolamento danificado"),
    ("Doc1", "rolamento_ball", "como identificar falta de lubrificação no rolamento"),
    ("Doc1", "rolamento_outer", "quais as frequências características de defeito em rolamentos"),
    ("Doc2", "desalinhado", "como corrigir o desalinhamento vertical do motor"),
    ("Doc2", "desalinhado", "o que é pé manco e como corrigir"),
    ("Doc2", "desalinhado", "quais os critérios de aceitação após o alinhamento"),
    ("Doc3", "desbalanceado", "como fazer o balanceamento dinâmico do rotor"),
    ("Doc3", "desbalanceado", "como calcular a massa de correção do desbalanceamento"),
    ("Doc3", "desbalanceado", "quais os sintomas de desbalanceamento em máquina rotativa"),
    ("Doc4", "correia", "como ajustar a tensão de uma correia frouxa"),
    ("Doc4", "correia", "qual o procedimento de substituição da correia"),
    ("Doc5", "polia", "como corrigir a excentricidade da polia"),
    ("Doc5", "polia", "como verificar o desgaste das ranhuras da polia"),
    ("Doc6", "cocked_rotor", "como corrigir um rotor inclinado montado incorretamente"),
    ("Doc6", "cocked_rotor", "como diferenciar cocked rotor de desbalanceamento"),
]

#: Perguntas curtas, no registro em que o técnico de fato escreve num chat.
PERTINENTES_CURTAS = [
    ("Doc6", "cocked_rotor", "o eixo pode estar empenado?"),
    ("Doc6", "cocked_rotor", "e o rolamento?"),
    ("Doc2", "desalinhado", "como alinho?"),
    ("Doc3", "desbalanceado", "preciso balancear?"),
    ("Doc1", "rolamento_inner", "o rolamento está ruim?"),
    ("Doc4", "correia", "a correia está frouxa?"),
    ("Doc5", "polia", "a polia está gasta?"),
    ("Doc1", "rolamento_ball", "falta lubrificação?"),
]

#: Perguntas técnicas legítimas cujo assunto não está no documento roteado. É o caso que
#: a segunda barreira precisa capturar: documento existe, resposta não.
IMPERTINENTES = [
    ("Doc1", "rolamento_inner", "como corrigir a falta de fase na alimentação trifásica"),
    ("Doc1", "rolamento_inner", "como dimensionar o inversor de frequência do acionamento"),
    ("Doc1", "rolamento_ball", "qual o procedimento de limpeza química do trocador de calor"),
    ("Doc2", "desalinhado", "como calcular a perda de carga na tubulação de recalque"),
    ("Doc2", "desalinhado", "como programar o CLP para intertravamento de segurança"),
    ("Doc3", "desbalanceado", "como fazer a manutenção do sistema hidráulico da prensa"),
    ("Doc3", "desbalanceado", "qual a norma aplicável para aterramento elétrico do painel"),
    ("Doc4", "correia", "como ajustar os parâmetros de soldagem MIG"),
    ("Doc4", "correia", "como interpretar o laudo de análise de óleo lubrificante"),
    ("Doc5", "polia", "como calibrar o transmissor de pressão diferencial"),
    ("Doc5", "polia", "qual o procedimento de teste hidrostático do vaso de pressão"),
    ("Doc6", "cocked_rotor", "como configurar a rede Profibus do supervisório"),
    ("Doc6", "cocked_rotor", "como corrigir a cavitação da bomba centrífuga"),
    ("Doc6", "cocked_rotor", "qual o intervalo de troca do filtro de ar comprimido"),
]

#: Perguntas curtas fora do escopo do documento roteado — o caso mais difícil, porque
#: perdem em massa semântica tanto quanto as curtas pertinentes.
IMPERTINENTES_CURTAS = [
    ("Doc6", "cocked_rotor", "e a rede Profibus?"),
    ("Doc1", "rolamento_inner", "e o filtro de ar?"),
    ("Doc3", "desbalanceado", "e o aterramento do painel?"),
    ("Doc2", "desalinhado", "e a soldagem MIG?"),
    ("Doc5", "polia", "e a pressão hidráulica?"),
    ("Doc4", "correia", "e o inversor de frequência?"),
]


def montar_casos() -> list[Caso]:
    return (
        [Caso(d, c, p, True) for d, c, p in PERTINENTES]
        + [Caso(d, c, p, True, curta=True) for d, c, p in PERTINENTES_CURTAS]
        + [Caso(d, c, p, False) for d, c, p in IMPERTINENTES]
        + [Caso(d, c, p, False, curta=True) for d, c, p in IMPERTINENTES_CURTAS]
    )


def medir(indice: IndiceDocumental) -> list[tuple[Caso, float]]:
    """Mede a relevância de cada caso exatamente como a produção mede.

    O número de trechos vem de :data:`TRECHOS_PADRAO`, e não de um literal: como a
    relevância registrada é o máximo entre os recuperados, medir com uma profundidade e
    operar com outra deslocaria o corte silenciosamente — a mesma armadilha que o
    cabeçalho deste módulo aponta para a formulação da consulta.
    """
    medidas: list[tuple[Caso, float]] = []
    for caso in montar_casos():
        consulta = montar_consulta(caso.condicao, caso.pergunta)
        recuperados = indice.buscar(consulta, documento=caso.documento, trechos=TRECHOS_PADRAO)
        medidas.append((caso, max((t.relevancia for t in recuperados), default=0.0)))
    return medidas


def escolher_limiar(medidas: list[tuple[Caso, float]]) -> tuple[float, dict]:
    """Escolhe o **piso**: o corte mais alto que ainda aceita toda pergunta pertinente.

    O critério é assimétrico de propósito, e essa é a decisão registrada no ADR-010-A.
    Uma versão anterior desta função maximizava um escore simétrico — fração de
    pertinentes aceitas mais fração de impertinentes barradas —, o que trata os dois
    erros como igualmente caros. Sobre o conjunto atual ela devolvia 0,8590 enquanto a
    produção operava em 0,8400: o script contradizia o código que dizia calibrar.

    Os dois erros não custam o mesmo. A recusa indevida é visível, frustra o técnico
    diante de uma pergunta legítima e ensina a não confiar no sistema. A passagem
    indevida é contida por três defesas que continuam de pé: a primeira barreira, que é
    determinística e resolve o caso central; o fato de o modelo receber apenas trechos do
    documento roteado; e a instrução de sistema, que exige declarar quando o procedimento
    não cobre o ponto perguntado.

    Daí o piso. Entre os cortes que aceitam 100% das pertinentes, escolhe-se o mais alto —
    barrando o máximo de impertinentes que ainda cabe sem recusar ninguém com razão.

    Os candidatos são os **pontos médios** entre valores medidos consecutivos, e não os
    valores em si: um limiar posto exatamente sobre uma medição fica à mercê da precisão
    de ponto flutuante, e a comparação ``>=`` passa a depender do último dígito.
    """
    pertinentes = [r for caso, r in medidas if caso.pertinente]
    impertinentes = [r for caso, r in medidas if not caso.pertinente]

    valores = sorted({r for _, r in medidas})
    candidatos = [(a + b) / 2 for a, b in zip(valores, valores[1:])]
    if not candidatos:
        return 0.0, {}

    def detalhar(limiar: float) -> dict:
        return {
            "pertinentes_aceitos": sum(1 for r in pertinentes if r >= limiar),
            "pertinentes_total": len(pertinentes),
            "impertinentes_rejeitados": sum(1 for r in impertinentes if r < limiar),
            "impertinentes_total": len(impertinentes),
            "margem": min(abs(limiar - v) for v in valores),
        }

    # O piso: o maior corte que não recusa nenhuma pergunta pertinente.
    aceitam_todas = [c for c in candidatos if all(r >= c for r in pertinentes)]
    if aceitam_todas:
        limiar = max(aceitam_todas)
        return limiar, detalhar(limiar)

    # Sem corte que aceite todas — só acontece se alguma pertinente pontuar abaixo da
    # menor medição, o que indica caso mal formulado. Cai no critério simétrico e o
    # relatório mostra o erro.
    melhor = max(
        candidatos,
        key=lambda c: (
            sum(1 for r in pertinentes if r >= c) / len(pertinentes)
            + sum(1 for r in impertinentes if r < c) / len(impertinentes),
            min(abs(c - v) for v in valores),
        ),
    )
    return melhor, detalhar(melhor)


def _resumir(rotulo: str, valores: list[float]) -> None:
    ordenados = sorted(valores)
    print(
        f"{rotulo:22} n={len(ordenados):2}  min={ordenados[0]:.4f}  "
        f"mediana={ordenados[len(ordenados) // 2]:.4f}  max={ordenados[-1]:.4f}"
    )


def main() -> int:
    faltando = {d for d in MAPA.values() if d} - {d for d, _, _ in PERTINENTES}
    if faltando:
        print(f"aviso: documentos sem caso pertinente: {sorted(faltando)}")

    indice = IndiceDocumental()
    if indice.garantir_indexado() == 0:
        print("base documental vazia — nada a calibrar")
        return 1

    medidas = medir(indice)
    pertinentes = [r for c, r in medidas if c.pertinente]
    impertinentes = [r for c, r in medidas if not c.pertinente]

    _resumir("pertinentes", pertinentes)
    _resumir("  longas", [r for c, r in medidas if c.pertinente and not c.curta])
    _resumir("  curtas", [r for c, r in medidas if c.pertinente and c.curta])
    _resumir("impertinentes", impertinentes)
    _resumir("  longas", [r for c, r in medidas if not c.pertinente and not c.curta])
    _resumir("  curtas", [r for c, r in medidas if not c.pertinente and c.curta])

    sobrepoe = max(impertinentes) >= min(pertinentes)
    print(f"\nsobreposição: {'SIM' if sobrepoe else 'NAO'}")

    limiar, detalhe = escolher_limiar(medidas)
    print(f"\nlimiar escolhido: {limiar:.4f}")
    print(
        f"  pertinentes aceitos ....... "
        f"{detalhe['pertinentes_aceitos']}/{detalhe['pertinentes_total']}"
    )
    print(
        f"  impertinentes rejeitados .. "
        f"{detalhe['impertinentes_rejeitados']}/{detalhe['impertinentes_total']}"
    )
    print(f"  margem ao caso mais proximo {detalhe['margem']:.4f}")

    print("\ndetalhe por caso:")
    for caso, relevancia in sorted(medidas, key=lambda m: -m[1]):
        marca = "+" if caso.pertinente else "-"
        decisao = "aceita" if relevancia >= limiar else "recusa"
        erro = "  <-- ERRO" if (relevancia >= limiar) != caso.pertinente else ""
        tipo = "curta" if caso.curta else "longa"
        print(
            f"  {marca} {relevancia:.4f} {decisao:7} {tipo} {caso.documento} | "
            f"{caso.pergunta[:46]}{erro}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
