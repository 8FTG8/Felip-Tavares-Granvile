"""Mapa entre condição canônica e documento técnico (ADR-010, ADR-011).

Este é o artefato que sustenta a primeira barreira do guardrail. A verificação de
respaldo documental é uma consulta a dicionário — não envolve modelo, não depende de
limiar e não pode ser contornada por formulação de pergunta. Se a condição não tem
documento aqui, o LLM não é acionado.

O mapa é declarado explicitamente, e não inferido por similaridade entre o nome do
defeito e o título do documento, porque a correspondência exige julgamento técnico que
nenhuma heurística textual faria corretamente: `eccentric_rotor` tem alta similaridade
lexical com a seção de excentricidade do Doc5, que trata de polias — e prescrever a
substituição de uma polia diante de um rotor excêntrico é precisamente a alucinação
plausível que o sistema existe para evitar.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.ingestion.rotulos import DEFEITOS, ESTADOS


@dataclass(frozen=True)
class Cobertura:
    """Situação documental de uma condição."""

    condicao: str
    documento: str | None
    justificativa: str

    @property
    def documentada(self) -> bool:
        return self.documento is not None


#: Condição canônica → documento que a cobre. ``None`` significa ausência de respaldo
#: documental e encaminha o evento ao caminho de recusa (ADR-004).
MAPA: dict[str, str | None] = {
    "rolamento_inner": "Doc1",
    "rolamento_outer": "Doc1",
    "rolamento_ball": "Doc1",
    "rolamento_combination": "Doc1",
    "desalinhado": "Doc2",
    "desbalanceado": "Doc3",
    "correia": "Doc4",
    "polia": "Doc5",
    "cocked_rotor": "Doc6",
    "eccentric_rotor": None,
    "ventoinha": None,
    "falta_fase": None,
}

#: Por que cada condição sem documento foi assim classificada. O texto acompanha a
#: resposta de recusa, para que o usuário entenda o motivo e saiba o que cadastrar.
JUSTIFICATIVAS: dict[str, str] = {
    "eccentric_rotor": (
        "A documentação disponível trata de excentricidade em polias (Doc5), não em "
        "rotores. São componentes distintos, com procedimentos de correção distintos: "
        "aplicar o procedimento de polia a um rotor excêntrico levaria a intervenção no "
        "componente errado."
    ),
    "ventoinha": (
        "Nenhum dos procedimentos disponíveis trata especificamente de falhas em "
        "ventoinhas. Ventiladores aparecem nos documentos apenas como exemplo de "
        "equipamento sujeito a outros modos de falha."
    ),
    "falta_fase": (
        "Trata-se de falha elétrica na alimentação trifásica. Todos os procedimentos "
        "disponíveis são de natureza mecânica — rolamentos, alinhamento, balanceamento, "
        "correias, polias e rotor."
    ),
}


def cobertura(condicao: str) -> Cobertura:
    """Situação documental de uma condição canônica."""
    if condicao in ESTADOS:
        return Cobertura(
            condicao=condicao,
            documento=None,
            justificativa=(
                "Estado operacional do sistema, não um defeito — não há falha a corrigir."
            ),
        )

    documento = MAPA.get(condicao)
    if documento is not None:
        return Cobertura(condicao=condicao, documento=documento, justificativa="")

    return Cobertura(
        condicao=condicao,
        documento=None,
        justificativa=JUSTIFICATIVAS.get(
            condicao,
            "Condição não reconhecida no histórico e sem procedimento técnico associado.",
        ),
    )


def condicoes_documentadas() -> set[str]:
    return {condicao for condicao, documento in MAPA.items() if documento is not None}


def condicoes_sem_documento() -> set[str]:
    return {condicao for condicao, documento in MAPA.items() if documento is None}


def validar_mapa() -> None:
    """Garante que o mapa cobre exatamente as famílias de defeito conhecidas.

    Invocado nos testes: uma família de defeito ausente do mapa cairia silenciosamente na
    recusa, e um defeito inexistente no mapa indicaria taxonomia desatualizada.
    """
    faltando = DEFEITOS - set(MAPA)
    sobrando = set(MAPA) - DEFEITOS
    if faltando or sobrando:
        raise ValueError(
            f"Mapa inconsistente com a taxonomia. Faltando: {sorted(faltando)}; "
            f"sobrando: {sorted(sobrando)}"
        )

    sem_justificativa = condicoes_sem_documento() - set(JUSTIFICATIVAS)
    if sem_justificativa:
        raise ValueError(
            "Condições sem documento precisam de justificativa explícita: "
            f"{sorted(sem_justificativa)}"
        )
