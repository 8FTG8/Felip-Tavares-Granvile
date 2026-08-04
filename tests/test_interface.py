"""Testes da interface (ADR-002).

Duas camadas. O cliente HTTP é testado contra um transporte simulado, sem rede — ele é
código de tradução e merece verificação determinística. As páginas são executadas pelo
``AppTest`` do Streamlit contra a API real, porque o que se quer saber é se a tela
renderiza sem exceção com dados verdadeiros; são marcadas como lentas e puladas quando o
serviço não está no ar.
"""

from __future__ import annotations

import json
from urllib.parse import quote

import httpx
import pytest

from app.cliente import ApiIndisponivel, ClienteApi

CITACOES = ["Doc6, seção 14 — Inspeção do Eixo", "Doc6, seção 16 — Correção da Falha"]


def _cliente_simulado(manipulador) -> ClienteApi:
    cliente = ClienteApi(base="http://api.local")
    transporte = httpx.MockTransport(manipulador)
    original = httpx.Client

    class ClienteComTransporte(original):  # type: ignore[misc,valid-type]
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transporte
            super().__init__(*args, **kwargs)

    httpx.Client = ClienteComTransporte  # type: ignore[misc]
    cliente._restaurar = lambda: setattr(httpx, "Client", original)  # type: ignore[attr-defined]
    return cliente


@pytest.fixture
def restaurar_httpx():
    original = httpx.Client
    yield
    httpx.Client = original


class TestClienteHttp:
    def test_analisar_envia_o_evento(self, restaurar_httpx) -> None:
        recebido = {}

        def manipulador(requisicao: httpx.Request) -> httpx.Response:
            recebido["url"] = str(requisicao.url)
            recebido["corpo"] = json.loads(requisicao.content)
            return httpx.Response(200, json={"caminho": "prescricao"})

        cliente = _cliente_simulado(manipulador)
        cliente.analisar({"fault": "cocked_rotor_2"}, "e o eixo?")

        assert recebido["url"].endswith("/eventos/analisar?pergunta=e%20o%20eixo%3F")
        assert recebido["corpo"]["fault"] == "cocked_rotor_2"

    def test_erro_da_api_vira_mensagem_legivel(self, restaurar_httpx) -> None:
        """A tela mostra o motivo da recusa, não um código HTTP."""

        def manipulador(requisicao: httpx.Request) -> httpx.Response:
            return httpx.Response(422, json={"detail": "'normal' é um estado operacional"})

        cliente = _cliente_simulado(manipulador)
        with pytest.raises(ValueError, match="estado operacional"):
            cliente.cadastrar_documento("normal", "p.pdf", b"conteudo")

    def test_api_fora_do_ar(self, restaurar_httpx) -> None:
        def manipulador(requisicao: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("recusada")

        cliente = _cliente_simulado(manipulador)
        with pytest.raises(ApiIndisponivel):
            cliente.estatisticas()

    def test_disponibilidade_nao_propaga_erro(self, restaurar_httpx) -> None:
        def manipulador(requisicao: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("recusada")

        assert _cliente_simulado(manipulador).disponivel() is False


class TestFluxoDeConversa:
    def test_roteamento_vem_dos_cabecalhos(self, restaurar_httpx) -> None:
        """Evita repetir a chamada só para obter as fontes, o que dobraria a geração."""

        def manipulador(requisicao: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text="Verifique o empenamento do eixo.",
                headers={
                    "X-Caminho": "prescricao",
                    "X-Condicao": "cocked_rotor",
                    "X-Documento": "Doc6",
                    "X-Fontes": quote(json.dumps(CITACOES, ensure_ascii=False)),
                },
            )

        cliente = _cliente_simulado(manipulador)
        texto = "".join(cliente.conversar_em_fluxo("e o eixo?", "cocked_rotor"))

        assert "empenamento" in texto
        assert cliente.ultimo_roteamento["caminho"] == "prescricao"
        assert cliente.ultimo_roteamento["documento"] == "Doc6"
        assert cliente.ultimo_roteamento["fontes"] == CITACOES

    def test_acentuacao_preservada_nos_cabecalhos(self, restaurar_httpx) -> None:
        """Cabeçalhos HTTP são latin-1; as citações vão codificadas em percentual."""

        def manipulador(requisicao: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text="ok",
                headers={"X-Fontes": quote(json.dumps(CITACOES, ensure_ascii=False))},
            )

        cliente = _cliente_simulado(manipulador)
        list(cliente.conversar_em_fluxo("e o eixo?", "cocked_rotor"))
        assert "seção" in cliente.ultimo_roteamento["fontes"][0]

    def test_roteamento_reiniciado_a_cada_consulta(self, restaurar_httpx) -> None:
        """Resíduo de uma conversa anterior exibiria fonte que não sustenta a resposta."""

        def manipulador(requisicao: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="ok", headers={"X-Caminho": "sem_documento"})

        cliente = _cliente_simulado(manipulador)
        cliente.ultimo_roteamento = {"fontes": ["resíduo"]}
        list(cliente.conversar_em_fluxo("como corrijo?", "falta_fase"))
        assert cliente.ultimo_roteamento["fontes"] == []


@pytest.mark.lento
class TestPaginas:
    """Executa a interface de verdade, contra a API no ar."""

    @pytest.fixture(autouse=True)
    def _exigir_api(self) -> None:
        if not ClienteApi().disponivel():
            pytest.skip("API fora do ar: suba com 'uvicorn src.api.app:app'")

    @pytest.mark.parametrize(
        "pagina", ["Painel", "Análise de evento", "Assistente técnico", "Base documental"]
    )
    def test_pagina_renderiza_sem_excecao(self, pagina: str) -> None:
        from streamlit.testing.v1 import AppTest

        teste = AppTest.from_file("app/main.py", default_timeout=120)
        teste.run()
        assert not teste.exception, teste.exception

        teste.button(key=f"nav_{pagina}").click().run()
        assert not teste.exception, teste.exception
        assert teste.session_state["pagina"] == pagina

    def test_navegacao_expoe_todos_os_destinos(self) -> None:
        from streamlit.testing.v1 import AppTest

        teste = AppTest.from_file("app/main.py", default_timeout=120)
        teste.run()

        chaves = {b.key for b in teste.button if b.key and b.key.startswith("nav_")}
        assert chaves == {
            "nav_Painel",
            "nav_Análise de evento",
            "nav_Assistente técnico",
            "nav_Base documental",
        }

    def test_destino_corrente_persiste_entre_execucoes(self) -> None:
        """Sem isso o usuário volta ao painel a cada interação na página."""
        from streamlit.testing.v1 import AppTest

        teste = AppTest.from_file("app/main.py", default_timeout=120)
        teste.run()
        teste.button(key="nav_Base documental").click().run()
        assert teste.session_state["pagina"] == "Base documental"

        teste.run()
        assert teste.session_state["pagina"] == "Base documental"

    def test_painel_exibe_a_cobertura(self) -> None:
        """A cobertura documental é o indicador que abre o painel — sem ele, a lacuna da
        base fica invisível."""
        from streamlit.testing.v1 import AppTest

        teste = AppTest.from_file("app/main.py", default_timeout=120)
        teste.run()
        conteudo = " ".join(bloco.value for bloco in teste.markdown)
        assert "Cobertura documental" in conteudo
        assert "Eventos monitorados" in conteudo

    def test_topo_declara_o_modelo_em_uso(self) -> None:
        """A demonstração precisa deixar explícito qual modelo está respondendo."""
        from streamlit.testing.v1 import AppTest

        teste = AppTest.from_file("app/main.py", default_timeout=120)
        teste.run()
        conteudo = " ".join(bloco.value for bloco in teste.markdown)
        assert "qwen2.5" in conteudo
