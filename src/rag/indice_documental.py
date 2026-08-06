"""Índice semântico da base documental (ADR-009, ADR-010).

Os 115 trechos dos seis procedimentos são representados por `multilingual-e5-large` e
armazenados em ChromaDB, que persiste em disco e dispensa serviço externo — coerente com
a operação em estação de trabalho única.

Duas particularidades da implementação merecem registro:

**Prefixos do e5.** O modelo foi treinado com marcadores assimétricos: documentos entram
como ``passage:`` e perguntas como ``query:``. Omiti-los degrada a recuperação de forma
silenciosa, sem erro algum — o índice apenas passa a devolver trechos piores.

**Filtro antes da busca.** A consulta é restrita ao documento que cobre a condição, e só
então o trecho mais relevante é procurado. Os seis procedimentos compartilham seções de
mesmo nome — Segurança, Registro da Intervenção, Recomendações Preventivas —, e uma busca
global recuperaria a seção certa do documento errado. Essa é a alucinação mais provável
neste projeto, e o filtro a elimina por construção em vez de por sorte.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection

from src.rag.documentos import Trecho, carregar_base_documental

RAIZ = Path(__file__).resolve().parents[2]
DIRETORIO_PERSISTENCIA = RAIZ / "storage" / "chroma"
COLECAO = "procedimentos_tecnicos"

MODELO_EMBEDDINGS = "intfloat/multilingual-e5-large"

#: Prefixos exigidos pelo e5. Ver nota no cabeçalho do módulo.
PREFIXO_DOCUMENTO = "passage: "
PREFIXO_CONSULTA = "query: "


@dataclass(frozen=True)
class TrechoRecuperado:
    """Trecho devolvido pela busca, com sua relevância para a consulta."""

    trecho: Trecho
    relevancia: float
    """Similaridade de cosseno em [0, 1] — quanto maior, mais pertinente."""

    @property
    def citacao(self) -> str:
        return self.trecho.citacao


@lru_cache(maxsize=1)
def _modelo():
    """Carrega o modelo de embeddings uma única vez por processo (~1,1 GB)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODELO_EMBEDDINGS)


class IndiceDocumental:
    """Recuperação semântica sobre os procedimentos técnicos."""

    def __init__(self, persistencia: Path | None = None, colecao: str = COLECAO) -> None:
        self._caminho = persistencia or DIRETORIO_PERSISTENCIA
        self._caminho.mkdir(parents=True, exist_ok=True)
        self._cliente = chromadb.PersistentClient(path=str(self._caminho))
        self._nome_colecao = colecao
        self._colecao: Collection = self._cliente.get_or_create_collection(
            name=colecao, metadata={"hnsw:space": "cosine"}
        )

    # -- indexação -----------------------------------------------------------------

    def indexar(self, trechos: tuple[Trecho, ...] | None = None, recriar: bool = False) -> int:
        """Indexa a base documental, devolvendo o número de trechos gravados.

        Com ``recriar``, a coleção é descartada e reconstruída — necessário quando o
        fatiamento ou o modelo de embeddings mudam, já que os vetores antigos deixam de
        ser comparáveis aos novos.
        """
        if recriar:
            self._cliente.delete_collection(self._nome_colecao)
            self._colecao = self._cliente.get_or_create_collection(
                name=self._nome_colecao, metadata={"hnsw:space": "cosine"}
            )

        base = trechos if trechos is not None else carregar_base_documental()
        if not base:
            return 0

        vetores = _modelo().encode(
            [PREFIXO_DOCUMENTO + t.conteudo_indexavel for t in base],
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        self._colecao.upsert(
            ids=[t.identificador for t in base],
            embeddings=[v.tolist() for v in vetores],
            documents=[t.texto for t in base],
            metadatas=[
                {
                    "documento": t.documento,
                    "titulo_documento": t.titulo_documento,
                    "numero_secao": t.numero_secao,
                    "titulo_secao": t.titulo_secao,
                    "origem": t.origem,
                }
                for t in base
            ],
        )
        return len(base)

    def remover_documento(self, documento: str) -> int:
        """Remove todos os trechos de um documento, devolvendo quantos saíram.

        Existe para o recadastro (ADR-010, ADR-014). ``indexar`` grava por ``upsert``, que
        atualiza os ids recebidos e **não apaga os ausentes**: um procedimento
        recadastrado com menos seções que o anterior deixaria as seções excedentes no
        índice, ainda associadas ao mesmo documento e ainda recuperáveis. A recomendação
        passaria a citar seção de procedimento revogado, com aparência de fonte legítima.

        A poda é responsabilidade de quem recadastra, não de :meth:`indexar`: a base
        entregue com o projeto é indexada por inteiro e não deve ser podada.
        """
        alvos = self._colecao.get(where={"documento": documento}, include=[])
        ids = alvos.get("ids") or []
        if ids:
            self._colecao.delete(ids=ids)
        return len(ids)

    def garantir_indexado(self) -> int:
        """Indexa apenas se a coleção estiver vazia."""
        if self._colecao.count() == 0:
            return self.indexar()
        return self._colecao.count()

    # -- consulta ------------------------------------------------------------------

    def buscar(
        self, pergunta: str, documento: str | None = None, trechos: int = 4
    ) -> list[TrechoRecuperado]:
        """Recupera os trechos mais relevantes para a pergunta.

        ``documento`` restringe a busca ao procedimento que cobre a condição — ver a nota
        sobre seções homônimas no cabeçalho do módulo. Sem restrição, a busca percorre
        toda a base, o que só faz sentido para exploração livre pelo usuário.
        """
        if self._colecao.count() == 0:
            return []

        vetor = _modelo().encode(
            PREFIXO_CONSULTA + pergunta, normalize_embeddings=True, show_progress_bar=False
        )

        resultado = self._colecao.query(
            query_embeddings=[vetor.tolist()],
            n_results=min(trechos, self._colecao.count()),
            where={"documento": documento} if documento else None,
        )

        if not resultado["ids"] or not resultado["ids"][0]:
            return []

        recuperados: list[TrechoRecuperado] = []
        for texto, metadados, distancia in zip(
            resultado["documents"][0], resultado["metadatas"][0], resultado["distances"][0]
        ):
            recuperados.append(
                TrechoRecuperado(
                    trecho=Trecho(
                        documento=str(metadados["documento"]),
                        titulo_documento=str(metadados["titulo_documento"]),
                        numero_secao=int(metadados["numero_secao"]),
                        titulo_secao=str(metadados["titulo_secao"]),
                        texto=texto,
                        origem=str(metadados["origem"]),
                    ),
                    # Chroma devolve distância de cosseno; a relevância é o complemento.
                    relevancia=1.0 - float(distancia),
                )
            )
        return recuperados

    # -- introspecção --------------------------------------------------------------

    @property
    def total_trechos(self) -> int:
        return self._colecao.count()

    def __repr__(self) -> str:
        return f"IndiceDocumental({self.total_trechos} trechos em {self._caminho.name})"
