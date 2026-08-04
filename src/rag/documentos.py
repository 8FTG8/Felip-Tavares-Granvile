"""Extração e fatiamento da base documental (ADR-009, ADR-012).

Os seis procedimentos técnicos fornecidos pela empresa são heterogêneos: cinco trazem
texto nativo extraível e o Doc1 é uma digitalização, 17 páginas de imagem sem camada de
texto. A extração escolhe a estratégia por documento — texto nativo quando existe, OCR
quando não existe — e o resultado é armazenado em cache, já que o OCR é lento.

O fatiamento segue as seções numeradas que os próprios autores impuseram ao conteúdo.
Cada seção é uma unidade semântica completa: um procedimento de correção passo a passo
chega inteiro ao modelo, nunca truncado no meio de uma sequência que o técnico precisa
seguir. Como subproduto, a citação de fonte fica verificável — "Doc1, seção 19" — o que
sustenta o requisito de rastreabilidade do ADR-004.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader

RAIZ = Path(__file__).resolve().parents[2]
DIRETORIO_DOCUMENTOS = RAIZ / "docs" / "dados"
DIRETORIO_CACHE = RAIZ / "data" / "processed"

#: Abaixo deste volume de caracteres por página, considera-se que o PDF não tem camada de
#: texto e recorre-se ao OCR. O Doc1 extrai zero caracteres em 17 páginas.
MINIMO_CARACTERES_POR_PAGINA = 100

#: Escala de rasterização para o OCR. Abaixo de 2x o reconhecimento degrada
#: perceptivelmente em textos de corpo pequeno.
ESCALA_OCR = 2.0


@dataclass(frozen=True)
class Trecho:
    """Uma seção de um documento, unidade de recuperação do índice semântico."""

    documento: str
    titulo_documento: str
    numero_secao: int
    titulo_secao: str
    texto: str
    origem: str
    """``nativo`` ou ``ocr`` — registra como o texto foi obtido."""

    @property
    def identificador(self) -> str:
        return f"{self.documento}#secao-{self.numero_secao}"

    @property
    def citacao(self) -> str:
        """Referência exibida ao usuário junto da recomendação."""
        return f"{self.documento}, seção {self.numero_secao} — {self.titulo_secao}"

    @property
    def conteudo_indexavel(self) -> str:
        """Texto enviado ao modelo de embeddings, com o cabeçalho preservado.

        Incluir título do documento e da seção melhora a recuperação: os seis
        procedimentos compartilham seções de mesmo nome, e o cabeçalho é o que as
        distingue no espaço vetorial.
        """
        return f"{self.titulo_documento} — {self.titulo_secao}\n\n{self.texto}"


def _normalizar_texto(texto: str) -> str:
    """Uniformiza espaços e quebras, preservando a separação entre parágrafos."""
    texto = unicodedata.normalize("NFC", texto)
    texto = texto.replace("\r\n", "\n").replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return "\n".join(linha.strip() for linha in texto.split("\n")).strip()


def _extrair_nativo(caminho: Path) -> str:
    leitor = PdfReader(caminho)
    return "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)


def _extrair_por_ocr(caminho: Path) -> str:
    """Rasteriza cada página e reconhece o texto (ADR-012).

    As importações são locais porque o OCR só é necessário para documentos
    digitalizados: quem trabalha apenas com os cinco PDFs nativos não paga o custo de
    carregar o runtime de reconhecimento.
    """
    import pypdfium2
    from rapidocr_onnxruntime import RapidOCR

    reconhecedor = RapidOCR()
    documento = pypdfium2.PdfDocument(caminho)
    paginas: list[str] = []

    for indice in range(len(documento)):
        imagem = documento[indice].render(scale=ESCALA_OCR).to_pil()
        resultado, _ = reconhecedor(imagem)
        if resultado:
            paginas.append("\n".join(linha[1] for linha in resultado))

    documento.close()
    return "\n".join(paginas)


def extrair_texto(caminho: Path, usar_cache: bool = True) -> tuple[str, str]:
    """Devolve o texto do documento e a origem da extração (``nativo`` ou ``ocr``)."""
    cache = DIRETORIO_CACHE / f"{caminho.stem}.txt"
    if usar_cache and cache.exists():
        conteudo = cache.read_text(encoding="utf-8")
        origem, _, texto = conteudo.partition("\n")
        return texto, origem.removeprefix("# origem: ")

    nativo = _extrair_nativo(caminho)
    paginas = len(PdfReader(caminho).pages)

    if len(nativo.strip()) >= MINIMO_CARACTERES_POR_PAGINA * paginas:
        texto, origem = _normalizar_texto(nativo), "nativo"
    else:
        texto, origem = _normalizar_texto(_extrair_por_ocr(caminho)), "ocr"

    if usar_cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(f"# origem: {origem}\n{texto}", encoding="utf-8")

    return texto, origem


#: Cabeçalho de seção: numeração no início da linha seguida de um título curto. O padrão
#: é deliberadamente tolerante — o OCR do Doc1 troca caracteres, e exigir inicial
#: maiúscula descartaria "1. 0bjetivo", lido com zero no lugar da letra O. A ambiguidade
#: resultante é resolvida em :func:`_secoes`, não aqui.
CABECALHO = re.compile(r"^(\d{1,2})\s*[\.\-–]?\s+([^\n]{3,80})$")


def _e_titulo_plausivel(titulo: str) -> bool:
    """Descarta itens de lista numerada, que têm a mesma forma de um cabeçalho.

    Um passo de procedimento é uma frase e termina em pontuação — "1. Desligar o
    equipamento." —, enquanto um título de seção não.
    """
    return bool(titulo) and titulo[-1] not in ".,;:" and any(c.isalpha() for c in titulo)


def _secoes(texto: str) -> list[tuple[int, str, int]]:
    """Localiza os cabeçalhos de seção do documento.

    Entre todos os candidatos, escolhe a **maior cadeia de numeração consecutiva** em
    ordem de documento. A escolha pelo comprimento é o que distingue a estrutura real de
    uma lista de passos embutida numa seção: o índice do documento forma uma cadeia longa
    (1, 2, 3, … 25), enquanto uma enumeração interna forma uma cadeia curta que reinicia.
    Buscar simplesmente a primeira sequência seria frágil — bastaria o OCR corromper um
    único cabeçalho para a detecção descarrilar para dentro de uma lista de passos.
    """
    candidatos: list[tuple[int, str, int]] = []
    for indice, linha in enumerate(texto.split("\n")):
        casamento = CABECALHO.match(linha.strip())
        if not casamento:
            continue
        titulo = casamento.group(2).strip()
        if _e_titulo_plausivel(titulo):
            candidatos.append((int(casamento.group(1)), titulo, indice))

    if not candidatos:
        return []

    # Maior cadeia crescente de passo 1, por programação dinâmica sobre os candidatos.
    comprimento = [1] * len(candidatos)
    anterior = [-1] * len(candidatos)
    for i in range(len(candidatos)):
        for j in range(i):
            if candidatos[j][0] == candidatos[i][0] - 1 and comprimento[j] + 1 > comprimento[i]:
                comprimento[i], anterior[i] = comprimento[j] + 1, j

    fim = max(range(len(candidatos)), key=lambda i: (comprimento[i], -candidatos[i][2]))
    cadeia: list[tuple[int, str, int]] = []
    while fim != -1:
        cadeia.append(candidatos[fim])
        fim = anterior[fim]

    return list(reversed(cadeia))


def _titulo_documento(texto: str, padrao: str, ate_linha: int | None = None) -> str:
    """Título do documento: tudo que precede a primeira seção numerada.

    Os procedimentos quebram o título em duas ou três linhas no PDF — "Procedimento para
    Correção de" / "Desalinhamento em Motor Elétrico" —, e reconstruí-lo por inteiro
    importa: o título compõe o texto indexado de cada trecho e é o que distingue seções
    homônimas de documentos diferentes no espaço vetorial.
    """
    linhas = texto.split("\n")[: ate_linha if ate_linha is not None else 5]
    titulo = " ".join(linha.strip() for linha in linhas if linha.strip())
    return titulo if len(titulo) > 15 else padrao


def fatiar(texto: str, documento: str, origem: str) -> list[Trecho]:
    """Divide o texto em trechos, um por seção numerada.

    Documentos sem seções detectáveis retornam um único trecho com o conteúdo integral —
    degradação preferível a fatiar arbitrariamente um procedimento técnico.
    """
    linhas = texto.split("\n")
    secoes = _secoes(texto)
    titulo = _titulo_documento(texto, documento, ate_linha=secoes[0][2] if secoes else None)

    if not secoes:
        return [
            Trecho(
                documento=documento,
                titulo_documento=titulo,
                numero_secao=0,
                titulo_secao="Documento completo",
                texto=texto,
                origem=origem,
            )
        ]

    trechos: list[Trecho] = []
    for posicao, (numero, titulo_secao, inicio) in enumerate(secoes):
        fim = secoes[posicao + 1][2] if posicao + 1 < len(secoes) else len(linhas)
        corpo = "\n".join(linhas[inicio + 1 : fim]).strip()
        if not corpo:
            continue
        trechos.append(
            Trecho(
                documento=documento,
                titulo_documento=titulo,
                numero_secao=numero,
                titulo_secao=titulo_secao,
                texto=corpo,
                origem=origem,
            )
        )

    return trechos


def carregar_documento(caminho: Path, usar_cache: bool = True) -> list[Trecho]:
    """Extrai e fatia um documento, devolvendo seus trechos."""
    texto, origem = extrair_texto(caminho, usar_cache=usar_cache)
    return fatiar(texto, documento=caminho.stem, origem=origem)


@lru_cache(maxsize=1)
def carregar_base_documental(diretorio: Path | None = None) -> tuple[Trecho, ...]:
    """Carrega todos os procedimentos técnicos disponíveis, em ordem de documento."""
    origem = diretorio or DIRETORIO_DOCUMENTOS
    trechos: list[Trecho] = []
    for caminho in sorted(origem.glob("Doc*.pdf")):
        trechos.extend(carregar_documento(caminho))
    return tuple(trechos)
