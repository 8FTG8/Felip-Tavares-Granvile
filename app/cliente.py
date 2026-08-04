"""Cliente HTTP da API de manutenção prescritiva (ADR-002).

A interface não importa os módulos do domínio: fala com a API pelos mesmos endpoints que
o supervisório usaria. A separação é o que sustenta a afirmação de que a API é o contrato
de integração — se a tela acessasse o índice diretamente, o desenho seria uma promessa
sem lastro, e um segundo cliente exigiria reescrever a lógica.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Iterator
from urllib.parse import unquote

import httpx

API_PADRAO = os.getenv("API_URL", "http://127.0.0.1:8000")

#: Análises e conversas podem levar dezenas de segundos em máquina sem GPU dedicada
#: (ADR-013). O tempo limite acompanha essa realidade em vez de fingir que não existe.
TEMPO_LIMITE = httpx.Timeout(300.0, connect=5.0)


class ApiIndisponivel(RuntimeError):
    """A API não respondeu. A interface orienta o usuário a subir o serviço."""


@dataclass
class ClienteApi:
    base: str = API_PADRAO
    ultimo_roteamento: dict = field(default_factory=dict)
    """Cabeçalhos da última resposta em fluxo: caminho, condição, documento e fontes."""

    def _url(self, caminho: str) -> str:
        return f"{self.base.rstrip('/')}{caminho}"

    def disponivel(self) -> bool:
        try:
            with httpx.Client(timeout=httpx.Timeout(3.0)) as cliente:
                return cliente.get(self._url("/openapi.json")).status_code == 200
        except httpx.HTTPError:
            return False

    def _post(self, caminho: str, **kwargs) -> dict:
        try:
            with httpx.Client(timeout=TEMPO_LIMITE) as cliente:
                resposta = cliente.post(self._url(caminho), **kwargs)
        except httpx.HTTPError as erro:
            raise ApiIndisponivel(str(erro)) from erro

        if resposta.status_code >= 400:
            detalhe = resposta.json().get("detail", resposta.text)
            raise ValueError(detalhe if isinstance(detalhe, str) else str(detalhe))
        return resposta.json()

    def _get(self, caminho: str) -> dict | list:
        try:
            with httpx.Client(timeout=TEMPO_LIMITE) as cliente:
                resposta = cliente.get(self._url(caminho))
        except httpx.HTTPError as erro:
            raise ApiIndisponivel(str(erro)) from erro
        resposta.raise_for_status()
        return resposta.json()

    # -- operações -----------------------------------------------------------------

    def analisar(self, evento: dict, pergunta: str | None = None) -> dict:
        parametros = {"pergunta": pergunta} if pergunta else None
        return self._post("/eventos/analisar", json=evento, params=parametros)

    def conversar(
        self, pergunta: str, condicao: str | None, historico: list[dict] | None = None
    ) -> dict:
        return self._post(
            "/chat",
            json={
                "pergunta": pergunta,
                "condicao": condicao,
                "historico": historico or [],
            },
        )

    def conversar_em_fluxo(
        self, pergunta: str, condicao: str | None, historico: list[dict] | None = None
    ) -> Iterator[str]:
        """Transmite a resposta em partes, para que a espera seja acompanhável.

        O roteamento e as citações chegam nos cabeçalhos, antes do primeiro token, e
        ficam em :attr:`ultimo_roteamento`. Consultá-los assim evita repetir a chamada
        só para obter as fontes — o que dobraria o tempo de geração.
        """
        corpo = {"pergunta": pergunta, "condicao": condicao, "historico": historico or []}
        self.ultimo_roteamento = {}
        try:
            with httpx.Client(timeout=TEMPO_LIMITE) as cliente:
                with cliente.stream("POST", self._url("/chat/fluxo"), json=corpo) as resposta:
                    resposta.raise_for_status()
                    self.ultimo_roteamento = {
                        "caminho": resposta.headers.get("x-caminho", ""),
                        "condicao": resposta.headers.get("x-condicao", ""),
                        "documento": resposta.headers.get("x-documento", ""),
                        "fontes": json.loads(unquote(resposta.headers.get("x-fontes", "[]"))),
                    }
                    for parte in resposta.iter_text():
                        if parte:
                            yield parte
        except httpx.HTTPError as erro:
            raise ApiIndisponivel(str(erro)) from erro

    def cadastrar_documento(self, condicao: str, nome: str, conteudo: bytes) -> dict:
        return self._post(
            "/documentos",
            data={"condicao": condicao},
            files={"arquivo": (nome, conteudo, "application/pdf")},
        )

    def cobertura(self) -> list[dict]:
        return self._get("/documentos/cobertura")  # type: ignore[return-value]

    def estatisticas(self) -> dict:
        return self._get("/estatisticas")  # type: ignore[return-value]
