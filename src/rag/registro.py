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
from collections.abc import Iterator
from contextlib import contextmanager
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


def _da_linha(linha: sqlite3.Row) -> DocumentoCadastrado:
    return DocumentoCadastrado(
        condicao=linha["condicao"],
        documento=linha["documento"],
        arquivo=linha["arquivo"],
        trechos=linha["trechos"],
        origem=linha["origem"],
        cadastrado_em=datetime.fromisoformat(linha["cadastrado_em"]),
    )


class RegistroDocumentos:
    """Associação persistente entre condição e documento cadastrado em operação."""

    def __init__(self, banco: Path | None = None) -> None:
        self._caminho = banco or BANCO_PADRAO
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conectar() as conexao:
            conexao.executescript(ESQUEMA)

    @contextmanager
    def _conectar(self) -> Iterator[sqlite3.Connection]:
        """Conexão por operação, com transação confirmada e arquivo liberado ao final.

        ``with sqlite3.connect(...)`` confirma a transação mas **não fecha** a conexão: os
        descritores ficavam abertos até o coletor de lixo passar, o que no Windows mantém
        o arquivo travado. Abrir por operação é adequado aqui — o registro é consultado a
        cada decisão do roteador, e uma conexão de curta duração dispensa a coordenação
        entre as várias threads em que o FastAPI executa as rotas síncronas.
        """
        conexao = sqlite3.connect(self._caminho)
        conexao.row_factory = sqlite3.Row
        try:
            with conexao:
                yield conexao
        finally:
            conexao.close()

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

    def remover(self, condicao: str) -> bool:
        """Apaga a associação de uma condição, devolvendo se havia alguma.

        O retorno existe para quem só precisa saber se havia. `src/rag/cadastro.py` não o
        usa porque decide antes, por :meth:`buscar` — de lá precisa também do caminho do
        arquivo, que a remoção tem de apagar.
        """
        with self._conectar() as conexao:
            cursor = conexao.execute(
                "DELETE FROM documentos_cadastrados WHERE condicao = ?", (condicao,)
            )
        return cursor.rowcount > 0

    def documento_de(self, condicao: str) -> str | None:
        with self._conectar() as conexao:
            linha = conexao.execute(
                "SELECT documento FROM documentos_cadastrados WHERE condicao = ?", (condicao,)
            ).fetchone()
        return linha["documento"] if linha else None

    def buscar(self, condicao: str) -> DocumentoCadastrado | None:
        """Cadastro completo de uma condição, com o caminho do arquivo em disco.

        A remoção precisa do caminho tal como foi gravado, e não recomposto a partir do
        identificador: quem gravou sabe onde pôs.
        """
        with self._conectar() as conexao:
            linha = conexao.execute(
                "SELECT * FROM documentos_cadastrados WHERE condicao = ?", (condicao,)
            ).fetchone()
        return _da_linha(linha) if linha else None

    def listar(self) -> list[DocumentoCadastrado]:
        with self._conectar() as conexao:
            linhas = conexao.execute(
                "SELECT * FROM documentos_cadastrados ORDER BY cadastrado_em DESC"
            ).fetchall()
        return [_da_linha(linha) for linha in linhas]

    def __len__(self) -> int:
        with self._conectar() as conexao:
            return conexao.execute("SELECT COUNT(*) FROM documentos_cadastrados").fetchone()[0]
