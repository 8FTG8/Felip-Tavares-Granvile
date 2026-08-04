"""Registro dos documentos cadastrados em operação (ADR-014).

O mapa de `src/rag/mapeamento.py` descreve a base documental entregue com o projeto: é
estático, versionado e revisto por quem conhece os procedimentos. Este módulo cobre o que
acontece *depois* — quando o sistema recusa um evento por falta de documentação e o
técnico atende ao pedido, cadastrando o procedimento que faltava.

Sem esta camada o convite ao cadastro seria vazio: o sistema pediria o documento e
continuaria recusando o mesmo defeito na consulta seguinte, porque a cobertura viveria
apenas no código-fonte.

A persistência é SQLite, embutido e sem serviço externo, coerente com a operação em
estação de trabalho única. O registro guarda a associação entre condição e documento, não
o conteúdo: o texto vai para o índice vetorial e o arquivo original para o disco, cada um
onde é consultado.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
BANCO_PADRAO = RAIZ / "storage" / "registro.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS documentos_cadastrados (
    condicao      TEXT PRIMARY KEY,
    documento     TEXT NOT NULL,
    arquivo       TEXT NOT NULL,
    trechos       INTEGER NOT NULL,
    origem        TEXT NOT NULL,
    cadastrado_em TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class DocumentoCadastrado:
    """Procedimento cadastrado em operação para uma condição antes descoberta."""

    condicao: str
    documento: str
    arquivo: str
    trechos: int
    origem: str
    cadastrado_em: datetime


class RegistroDocumentos:
    """Associação persistente entre condição e documento cadastrado em operação."""

    def __init__(self, banco: Path | None = None) -> None:
        self._caminho = banco or BANCO_PADRAO
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conectar() as conexao:
            conexao.executescript(ESQUEMA)

    def _conectar(self) -> sqlite3.Connection:
        conexao = sqlite3.connect(self._caminho)
        conexao.row_factory = sqlite3.Row
        return conexao

    def registrar(
        self, condicao: str, documento: str, arquivo: str, trechos: int, origem: str
    ) -> DocumentoCadastrado:
        """Associa um documento a uma condição, substituindo cadastro anterior.

        A substituição é intencional: cadastrar de novo para a mesma condição significa
        corrigir ou atualizar o procedimento, e manter as duas versões faria a busca
        recuperar texto obsoleto sem que ninguém percebesse.
        """
        momento = datetime.now(timezone.utc)
        with self._conectar() as conexao:
            conexao.execute(
                "INSERT INTO documentos_cadastrados "
                "(condicao, documento, arquivo, trechos, origem, cadastrado_em) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(condicao) DO UPDATE SET "
                "documento=excluded.documento, arquivo=excluded.arquivo, "
                "trechos=excluded.trechos, origem=excluded.origem, "
                "cadastrado_em=excluded.cadastrado_em",
                (condicao, documento, arquivo, trechos, origem, momento.isoformat()),
            )
        return DocumentoCadastrado(condicao, documento, arquivo, trechos, origem, momento)

    def documento_de(self, condicao: str) -> str | None:
        with self._conectar() as conexao:
            linha = conexao.execute(
                "SELECT documento FROM documentos_cadastrados WHERE condicao = ?", (condicao,)
            ).fetchone()
        return linha["documento"] if linha else None

    def listar(self) -> list[DocumentoCadastrado]:
        with self._conectar() as conexao:
            linhas = conexao.execute(
                "SELECT * FROM documentos_cadastrados ORDER BY cadastrado_em DESC"
            ).fetchall()
        return [
            DocumentoCadastrado(
                condicao=linha["condicao"],
                documento=linha["documento"],
                arquivo=linha["arquivo"],
                trechos=linha["trechos"],
                origem=linha["origem"],
                cadastrado_em=datetime.fromisoformat(linha["cadastrado_em"]),
            )
            for linha in linhas
        ]

    def remover(self, condicao: str) -> bool:
        with self._conectar() as conexao:
            cursor = conexao.execute(
                "DELETE FROM documentos_cadastrados WHERE condicao = ?", (condicao,)
            )
        return cursor.rowcount > 0

    def __len__(self) -> int:
        with self._conectar() as conexao:
            return conexao.execute("SELECT COUNT(*) FROM documentos_cadastrados").fetchone()[0]
