"""Normalização canônica dos rótulos de falha (ADR-005).

A coluna ``fault`` do ``banner.csv`` contém 151 rótulos distintos que correspondem a
apenas 17 condições reais — 12 famílias de defeito e 5 estados do sistema. A dispersão
vem de três fontes:

1. sufixos de sessão de coleta: ``_2``, ``_pos_2``, ``_carga_3``, ``_adxl_0``;
2. prefixos e sufixos de lote: ``new_*``, ``_novo``, ``_antigo_1``;
3. erros de digitação do operador, já que a anotação é manual.

Este módulo converte o rótulo bruto na sua forma canônica e classifica o resultado como
defeito, estado ou desconhecido. Todo o roteamento documental e o guardrail dependem
desta camada: sem ela, 421 eventos que possuem documentação seriam recusados por engano.

A correção dos erros de digitação é feita por aliases declarados um a um, nunca por
distância de edição — ``desalinhado`` e ``desbalanceado`` estão a poucas edições um do
outro, e confundi-los seria um erro grave e silencioso.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

DESCONHECIDO = "desconhecido"


class TipoCondicao(str, Enum):
    """Natureza da condição registrada no evento."""

    DEFEITO = "defeito"
    ESTADO = "estado"
    DESCONHECIDO = "desconhecido"


@dataclass(frozen=True)
class Condicao:
    """Resultado da normalização de um rótulo bruto."""

    bruto: str
    canonico: str
    tipo: TipoCondicao

    @property
    def e_defeito(self) -> bool:
        return self.tipo is TipoCondicao.DEFEITO


#: Famílias de defeito reconhecidas (12).
DEFEITOS: frozenset[str] = frozenset(
    {
        "rolamento_inner",
        "rolamento_outer",
        "rolamento_ball",
        "rolamento_combination",
        "cocked_rotor",
        "eccentric_rotor",
        "desbalanceado",
        "desalinhado",
        "ventoinha",
        "polia",
        "correia",
        "falta_fase",
    }
)

#: Estados do sistema (5). O enunciado determina que não representam problemas.
ESTADOS: frozenset[str] = frozenset(
    {
        "normal",
        "motor_desligado",
        "teste",
        "baseline",
        "acelerando",
    }
)

#: Erros de digitação do operador, corrigidos por alias explícito para a forma que o
#: rótulo teria caso escrito corretamente. Mantém-se o sufixo de sessão original para
#: que a remoção de sufixos siga o mesmo caminho dos demais rótulos.
ALIASES_TIPOGRAFICOS: dict[str, str] = {
    "cockecocked_adxl_0": "cocked_adxl_0",
    "ddesbalanceado_adxl_0": "desbalanceado_adxl_0",
    "dedesbalanceado_adxl_1": "desbalanceado_adxl_1",
    "desabalanceado_3": "desbalanceado_3",
    "desbalanceamento": "desbalanceado",
    "desbanlanceado_carga_3_2": "desbalanceado_carga_3_2",
    "mortor_desligado_novo": "motor_desligado_novo",
    "new_desabanceado_1": "new_desbalanceado_1",
    "new_tes": "new_teste",
    "normla_carga_3_3": "normal_carga_3_3",
}

#: Prefixos de lote removidos antes da análise do radical.
PREFIXOS = (re.compile(r"^new_"),)

#: Sufixos de sessão de coleta, aplicados repetidamente até a forma estabilizar. A ordem
#: importa: os sufixos compostos precisam ser testados antes do numérico simples, sob
#: pena de ``desbalanceado_antigo_0`` degenerar em ``desbalanceado_antigo``.
SUFIXOS = (
    re.compile(r"_pos_\d+$"),
    re.compile(r"_adxl_\d+$"),
    re.compile(r"_antigo_\d+$"),
    re.compile(r"_carga_\d+$"),
    re.compile(r"_carga$"),
    re.compile(r"_novo_teste$"),
    re.compile(r"_novo$"),
    re.compile(r"_\d+$"),
)

#: Radicais que, depois da limpeza, ainda não coincidem com a forma canônica. Cobrem
#: abreviações usadas pelo operador e variantes de nomenclatura do mesmo defeito.
RADICAIS: dict[str, str] = {
    "rolamento_comb": "rolamento_combination",
    "cocked": "cocked_rotor",
    "eccentric": "eccentric_rotor",
    "desbalanceado_1parafuso": "desbalanceado",
}


def _limpar(rotulo: str) -> str:
    """Remove prefixos de lote e sufixos de sessão até a forma estabilizar."""
    forma = rotulo
    while True:
        anterior = forma
        for prefixo in PREFIXOS:
            forma = prefixo.sub("", forma)
        for sufixo in SUFIXOS:
            forma = sufixo.sub("", forma)
        if forma == anterior:
            return forma


def normalizar(rotulo: str | None) -> Condicao:
    """Converte um rótulo bruto de ``fault`` na condição canônica correspondente.

    Rótulos não reconhecidos retornam :data:`DESCONHECIDO` com tipo
    :attr:`TipoCondicao.DESCONHECIDO`, o que encaminha o evento ao caminho de "defeito
    sem documentação" (ADR-006) — o comportamento desejado para uma condição nova.
    """
    if rotulo is None:
        return Condicao(bruto="", canonico=DESCONHECIDO, tipo=TipoCondicao.DESCONHECIDO)

    bruto = rotulo.strip()
    forma = ALIASES_TIPOGRAFICOS.get(bruto.lower(), bruto.lower())
    forma = _limpar(forma)
    canonico = RADICAIS.get(forma, forma)

    if canonico in DEFEITOS:
        return Condicao(bruto=bruto, canonico=canonico, tipo=TipoCondicao.DEFEITO)
    if canonico in ESTADOS:
        return Condicao(bruto=bruto, canonico=canonico, tipo=TipoCondicao.ESTADO)
    return Condicao(bruto=bruto, canonico=DESCONHECIDO, tipo=TipoCondicao.DESCONHECIDO)


def e_defeito(rotulo: str | None) -> bool:
    """Atalho para verificar se o rótulo bruto corresponde a um defeito."""
    return normalizar(rotulo).e_defeito
