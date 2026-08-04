"""Gera a amostra estratificada do ``banner.csv`` versionada no repositório.

O conjunto completo tem 32 MB e é distribuído pelo Google Drive indicado no enunciado.
Para que o repositório permaneça clonável e os testes rodem sem download, versiona-se uma
amostra estratificada **por rótulo bruto** — não por condição canônica —, de modo que os
151 rótulos originais, incluindo os erros de digitação do operador, estejam representados.

Uso::

    python scripts/gerar_amostra.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "docs" / "dados" / "banner.csv"
DESTINO = RAIZ / "data" / "amostra_banner.csv"

#: Mínimo de eventos por rótulo bruto. Garante que rótulos raros — ``acelerando`` (7
#: eventos), ``new_teste`` (2) — sobrevivam à amostragem.
MINIMO_POR_ROTULO = 5

#: Alvo aproximado de linhas na amostra.
ALVO = 5_000


def gerar(origem: Path, destino: Path, alvo: int, semente: int = 42) -> pd.DataFrame:
    completo = pd.read_csv(origem)
    fracao = alvo / len(completo)

    partes = [
        grupo.sample(
            n=min(len(grupo), max(MINIMO_POR_ROTULO, round(len(grupo) * fracao))),
            random_state=semente,
        )
        for _, grupo in completo.groupby("fault", sort=False)
    ]
    amostra = (
        pd.concat(partes).sort_values("created_at").reset_index(drop=True)
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    amostra.to_csv(destino, index=False)
    return amostra


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alvo", type=int, default=ALVO, help="linhas aproximadas")
    parser.add_argument("--semente", type=int, default=42)
    args = parser.parse_args()

    amostra = gerar(ORIGEM, DESTINO, args.alvo, args.semente)
    completo_rotulos = pd.read_csv(ORIGEM, usecols=["fault"])["fault"].nunique()

    print(f"amostra gerada: {DESTINO.relative_to(RAIZ)}")
    print(f"  linhas ............ {len(amostra):,}")
    print(f"  rótulos brutos .... {amostra['fault'].nunique()} de {completo_rotulos}")
    print(f"  tamanho ........... {DESTINO.stat().st_size / 1_048_576:.1f} MB")


if __name__ == "__main__":
    main()
