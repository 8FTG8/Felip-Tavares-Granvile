"""Testes do cadastro de procedimentos em operação (ADR-014).

O teste decisivo aqui é o de ciclo completo: o sistema recusa um defeito por falta de
documentação, o técnico cadastra o procedimento que faltava, e o mesmo evento passa a
receber prescrição. Sem ele, a instrução "registre um documento" seria uma promessa não
verificada.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencias import (
    obter_gerador,
    obter_indice_documental,
    obter_indice_similaridade,
    obter_registro,
    obter_roteador,
)
from src.rag.cadastro import CadastroInvalido, validar_condicao
from src.rag.documentos import DIRETORIO_DOCUMENTOS
from src.rag.gerador import Gerador
from src.rag.indice_documental import IndiceDocumental
from src.rag.registro import RegistroDocumentos
from src.rag.roteador import Roteador
from tests.test_api_eventos import SimilaridadeFalsa
from tests.test_gerador import ClienteFalso
from tests.test_indice import EVENTO_DO_ENUNCIADO
from tests.test_roteador import IndiceFalso

PROCEDIMENTO = DIRETORIO_DOCUMENTOS / "Doc2.pdf"

#: Par de procedimentos com contagens de seção diferentes, para exercitar o recadastro.
#: Doc4 tem 19 seções e Doc2, 16 — a redução é o que expõe trecho obsoleto sobrevivente.
DOCUMENTO_MAIOR = DIRETORIO_DOCUMENTOS / "Doc4.pdf"
DOCUMENTO_MENOR = PROCEDIMENTO
SECOES_MENOR = 16


def _pular_sem_base() -> None:
    if not PROCEDIMENTO.exists() or not DOCUMENTO_MAIOR.exists():
        pytest.skip("base documental ausente")


@pytest.fixture
def registro(tmp_path: Path) -> RegistroDocumentos:
    return RegistroDocumentos(tmp_path / "registro.db")


@pytest.fixture
def indice_documental() -> IndiceFalso:
    return IndiceFalso()


@pytest.fixture
def cliente(registro: RegistroDocumentos, indice_documental: IndiceFalso) -> TestClient:
    """API com registro isolado e roteador ciente dele."""
    app.dependency_overrides[obter_indice_similaridade] = lambda: SimilaridadeFalsa()
    app.dependency_overrides[obter_indice_documental] = lambda: indice_documental
    app.dependency_overrides[obter_registro] = lambda: registro
    app.dependency_overrides[obter_roteador] = lambda: Roteador(
        indice_documental, registro=registro
    )
    app.dependency_overrides[obter_gerador] = lambda: Gerador(cliente=ClienteFalso())
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestRegistro:
    """Métodos do registro que a rota de remoção usa diretamente."""

    def test_buscar_devolve_o_caminho_gravado(self, registro: RegistroDocumentos) -> None:
        registro.registrar("ventoinha", "DocOp-ventoinha", "/tmp/x.pdf", 16, "nativo")
        achado = registro.buscar("ventoinha")
        assert achado is not None
        assert achado.arquivo == "/tmp/x.pdf"

    def test_buscar_sem_cadastro(self, registro: RegistroDocumentos) -> None:
        assert registro.buscar("ventoinha") is None

    def test_remover_informa_se_havia(self, registro: RegistroDocumentos) -> None:
        """O retorno distingue "removi" de "não havia nada"."""
        registro.registrar("ventoinha", "DocOp-ventoinha", "/tmp/x.pdf", 16, "nativo")
        assert registro.remover("ventoinha") is True
        assert registro.remover("ventoinha") is False
        assert len(registro) == 0


class TestValidacaoDaCondicao:
    def test_aceita_defeito_conhecido(self) -> None:
        assert validar_condicao("ventoinha") == "ventoinha"

    def test_aceita_rotulo_bruto_do_operador(self) -> None:
        """O técnico pode informar o rótulo como o vê no sistema."""
        assert validar_condicao("new_falta_fase_0") == "falta_fase"

    def test_recusa_estado(self) -> None:
        """Estado não tem falha a corrigir — cadastrar procedimento não faz sentido."""
        with pytest.raises(CadastroInvalido, match="estado operacional"):
            validar_condicao("normal")

    def test_recusa_condicao_inexistente(self) -> None:
        """Um nome livre criaria condição fantasma, jamais alcançada por evento algum."""
        with pytest.raises(CadastroInvalido, match="não corresponde"):
            validar_condicao("cavitacao")


class TestCadastro:
    def test_cadastra_e_indexa(self, cliente: TestClient) -> None:
        _pular_sem_base()
        with PROCEDIMENTO.open("rb") as arquivo:
            resposta = cliente.post(
                "/documentos",
                data={"condicao": "ventoinha"},
                files={"arquivo": ("procedimento.pdf", arquivo, "application/pdf")},
            )
        assert resposta.status_code == 201
        corpo = resposta.json()
        assert corpo["condicao"] == "ventoinha"
        assert corpo["documento"].startswith("DocOp-")
        assert corpo["trechos"] == 16
        assert corpo["secoes"]

    def test_registra_a_associacao(
        self, cliente: TestClient, registro: RegistroDocumentos
    ) -> None:
        _pular_sem_base()
        with PROCEDIMENTO.open("rb") as arquivo:
            cliente.post(
                "/documentos",
                data={"condicao": "ventoinha"},
                files={"arquivo": ("p.pdf", arquivo, "application/pdf")},
            )
        assert registro.documento_de("ventoinha") == "DocOp-ventoinha"

    def test_recadastro_substitui(
        self, cliente: TestClient, registro: RegistroDocumentos
    ) -> None:
        """Cadastrar de novo é corrigir o procedimento; manter as duas versões faria a
        busca recuperar texto obsoleto sem que ninguém percebesse."""
        _pular_sem_base()
        for _ in range(2):
            with PROCEDIMENTO.open("rb") as arquivo:
                cliente.post(
                    "/documentos",
                    data={"condicao": "ventoinha"},
                    files={"arquivo": ("p.pdf", arquivo, "application/pdf")},
                )
        assert len(registro) == 1

    def test_recadastro_nao_deixa_secao_obsoleta_no_indice(
        self, cliente: TestClient, indice_documental: IndiceFalso
    ) -> None:
        """O procedimento substituído sai do índice por inteiro.

        O ``upsert`` atualiza os ids recebidos e não apaga os ausentes. Recadastrar com
        menos seções que o anterior deixava as excedentes recuperáveis, ainda associadas
        ao mesmo documento: a prescrição passaria a citar seção de procedimento revogado,
        com aparência de fonte legítima. Repetir o mesmo arquivo não exporia a falha —
        daí os dois documentos terem contagens de seção diferentes.
        """
        _pular_sem_base()
        for origem in (DOCUMENTO_MAIOR, DOCUMENTO_MENOR):
            with origem.open("rb") as arquivo:
                resposta = cliente.post(
                    "/documentos",
                    data={"condicao": "ventoinha"},
                    files={"arquivo": ("p.pdf", arquivo, "application/pdf")},
                )
                assert resposta.status_code == 201

        assert len(indice_documental.indexados) == SECOES_MENOR
        assert max(t.numero_secao for t in indice_documental.indexados) == SECOES_MENOR

    def test_envio_ilegivel_preserva_o_cadastro_anterior(
        self, cliente: TestClient, registro: RegistroDocumentos, indice_documental: IndiceFalso
    ) -> None:
        """Um envio inválido é recusado antes de tocar em qualquer estado.

        A ordem anterior gravava o PDF por cima do destino e só então tentava extrair,
        apagando o arquivo ao falhar: um upload ruim destruía o procedimento válido que
        estava cadastrado, enquanto registro e índice seguiam apontando para ele.
        """
        _pular_sem_base()
        with DOCUMENTO_MENOR.open("rb") as arquivo:
            cliente.post(
                "/documentos",
                data={"condicao": "ventoinha"},
                files={"arquivo": ("p.pdf", arquivo, "application/pdf")},
            )

        resposta = cliente.post(
            "/documentos",
            data={"condicao": "ventoinha"},
            files={"arquivo": ("corrompido.pdf", b"isto nao e um pdf", "application/pdf")},
        )

        assert resposta.status_code == 422
        assert "PDF" in resposta.json()["detail"]
        assert registro.documento_de("ventoinha") == "DocOp-ventoinha"
        assert len(indice_documental.indexados) == SECOES_MENOR
        assert Path(registro.listar()[0].arquivo).exists()

    def test_recusa_arquivo_nao_pdf(self, cliente: TestClient) -> None:
        resposta = cliente.post(
            "/documentos",
            data={"condicao": "ventoinha"},
            files={"arquivo": ("nota.txt", b"texto qualquer", "text/plain")},
        )
        assert resposta.status_code == 415

    def test_recusa_estado(self, cliente: TestClient) -> None:
        _pular_sem_base()
        with PROCEDIMENTO.open("rb") as arquivo:
            resposta = cliente.post(
                "/documentos",
                data={"condicao": "normal"},
                files={"arquivo": ("p.pdf", arquivo, "application/pdf")},
            )
        assert resposta.status_code == 422

    def test_recusa_condicao_inexistente(self, cliente: TestClient) -> None:
        _pular_sem_base()
        with PROCEDIMENTO.open("rb") as arquivo:
            resposta = cliente.post(
                "/documentos",
                data={"condicao": "cavitacao"},
                files={"arquivo": ("p.pdf", arquivo, "application/pdf")},
            )
        assert resposta.status_code == 422


class TestCobertura:
    def test_lista_todas_as_familias(self, cliente: TestClient) -> None:
        corpo = cliente.get("/documentos/cobertura").json()
        assert len(corpo) == 12

    def test_situacao_inicial(self, cliente: TestClient) -> None:
        sem_documento = {
            x["condicao"] for x in cliente.get("/documentos/cobertura").json()
            if not x["documentada"]
        }
        assert sem_documento == {"eccentric_rotor", "falta_fase", "ventoinha"}

    def test_justificativa_acompanha_a_ausencia(self, cliente: TestClient) -> None:
        corpo = cliente.get("/documentos/cobertura").json()
        for situacao in corpo:
            if not situacao["documentada"]:
                assert situacao["justificativa"]

    def test_cadastro_altera_a_cobertura(self, cliente: TestClient) -> None:
        _pular_sem_base()
        with PROCEDIMENTO.open("rb") as arquivo:
            cliente.post(
                "/documentos",
                data={"condicao": "ventoinha"},
                files={"arquivo": ("p.pdf", arquivo, "application/pdf")},
            )
        situacoes = {x["condicao"]: x for x in cliente.get("/documentos/cobertura").json()}
        assert situacoes["ventoinha"]["documentada"]
        assert situacoes["ventoinha"]["cadastrado_em_operacao"]
        assert not situacoes["falta_fase"]["documentada"]


class TestCicloCompletoDoGuardrail:
    """Recusa → cadastro → atendimento. O que torna verdadeira a instrução da recusa."""

    def test_defeito_sem_documento_passa_a_ser_atendido(self, cliente: TestClient) -> None:
        _pular_sem_base()
        evento = EVENTO_DO_ENUNCIADO | {"fault": "ventoinha_2"}

        antes = cliente.post("/eventos/analisar", json=evento).json()
        assert antes["caminho"] == "sem_documento"
        assert "registre um documento" in antes["recomendacao"].lower()

        with PROCEDIMENTO.open("rb") as arquivo:
            cadastro = cliente.post(
                "/documentos",
                data={"condicao": "ventoinha"},
                files={"arquivo": ("procedimento_ventoinha.pdf", arquivo, "application/pdf")},
            )
        assert cadastro.status_code == 201

        depois = cliente.post("/eventos/analisar", json=evento).json()
        assert depois["caminho"] == "prescricao"
        assert depois["documento"] == "DocOp-ventoinha"
        assert depois["fontes"]

    def test_cadastro_nao_sobrepoe_documento_do_mapa(self, cliente: TestClient) -> None:
        """O mapa vence: o registro preenche lacunas, não substitui a base entregue.

        Este ADR e a docstring de `Roteador._cobertura` declararam por muito tempo a
        precedência invertida — "um cadastro em operação sobrepõe-se ao mapa" —, e nenhum
        teste tocava o caso, porque a demonstração só cadastra para condição descoberta.
        Trocar um procedimento revisto por um PDF enviado em operação exige alterar o
        mapa, que passa por revisão de código (ADR-014).
        """
        _pular_sem_base()
        _cadastrar(cliente, "desalinhado")

        situacoes = {x["condicao"]: x for x in cliente.get("/documentos/cobertura").json()}
        assert situacoes["desalinhado"]["documento"] == "Doc2"
        assert not situacoes["desalinhado"]["cadastrado_em_operacao"]

        evento = EVENTO_DO_ENUNCIADO | {"fault": "desalinhado"}
        assert cliente.post("/eventos/analisar", json=evento).json()["documento"] == "Doc2"

    def test_cadastro_nao_afeta_outros_defeitos(self, cliente: TestClient) -> None:
        """A cobertura acrescentada é específica: `falta_fase` continua recusada."""
        _pular_sem_base()
        with PROCEDIMENTO.open("rb") as arquivo:
            cliente.post(
                "/documentos",
                data={"condicao": "ventoinha"},
                files={"arquivo": ("p.pdf", arquivo, "application/pdf")},
            )
        evento = EVENTO_DO_ENUNCIADO | {"fault": "new_falta_fase_0"}
        assert cliente.post("/eventos/analisar", json=evento).json()["caminho"] == "sem_documento"


def _cadastrar(cliente: TestClient, condicao: str, origem: Path = PROCEDIMENTO) -> None:
    with origem.open("rb") as arquivo:
        resposta = cliente.post(
            "/documentos",
            data={"condicao": condicao},
            files={"arquivo": ("p.pdf", arquivo, "application/pdf")},
        )
    assert resposta.status_code == 201


class TestRemocao:
    """Desfazer um cadastro feito em operação (ADR-014).

    Cadastrar na condição errada é erro banal de operação, e antes desta rota a única
    saída era mexer no índice, no SQLite e no disco por fora, com reinício do serviço.
    """

    def test_devolve_a_condicao_a_recusa(self, cliente: TestClient) -> None:
        """O ciclo do ADR-014 ao contrário — o teste que sustenta a rota.

        Sem ele, "removi" seria uma linha apagada no banco; o que precisa ser verificado é
        que o mesmo evento volta a ser recusado por falta de documentação.
        """
        _pular_sem_base()
        evento = EVENTO_DO_ENUNCIADO | {"fault": "ventoinha_2"}

        _cadastrar(cliente, "ventoinha")
        assert cliente.post("/eventos/analisar", json=evento).json()["caminho"] == "prescricao"

        resposta = cliente.delete("/documentos/ventoinha")
        assert resposta.status_code == 200
        assert resposta.json()["documento"] == "DocOp-ventoinha"
        assert resposta.json()["trechos_removidos"] == SECOES_MENOR

        depois = cliente.post("/eventos/analisar", json=evento).json()
        assert depois["caminho"] == "sem_documento"
        assert "registre um documento" in depois["recomendacao"].lower()

    def test_esvazia_o_indice_do_documento(
        self, cliente: TestClient, indice_documental: IndiceFalso
    ) -> None:
        """Nenhum trecho sobrevive à remoção.

        É a mesma falha da ADR-014: trecho órfão no índice continua sendo
        recuperado e citado como fonte legítima de um documento que já não existe.
        """
        _pular_sem_base()
        _cadastrar(cliente, "ventoinha")
        assert indice_documental.indexados

        cliente.delete("/documentos/ventoinha")
        assert indice_documental.indexados == []

    def test_nao_toca_outro_documento(
        self, cliente: TestClient, registro: RegistroDocumentos, indice_documental: IndiceFalso
    ) -> None:
        _pular_sem_base()
        _cadastrar(cliente, "ventoinha", DOCUMENTO_MENOR)
        _cadastrar(cliente, "falta_fase", DOCUMENTO_MAIOR)

        cliente.delete("/documentos/ventoinha")

        assert registro.documento_de("falta_fase") == "DocOp-falta_fase"
        restantes = {t.documento for t in indice_documental.indexados}
        assert restantes == {"DocOp-falta_fase"}

    def test_apaga_o_arquivo_em_disco(
        self, cliente: TestClient, registro: RegistroDocumentos
    ) -> None:
        _pular_sem_base()
        _cadastrar(cliente, "ventoinha")
        arquivo = Path(registro.listar()[0].arquivo)
        assert arquivo.exists()

        cliente.delete("/documentos/ventoinha")
        assert not arquivo.exists()

    def test_altera_a_cobertura(self, cliente: TestClient) -> None:
        _pular_sem_base()
        _cadastrar(cliente, "ventoinha")
        cliente.delete("/documentos/ventoinha")

        situacoes = {x["condicao"]: x for x in cliente.get("/documentos/cobertura").json()}
        assert not situacoes["ventoinha"]["documentada"]
        assert situacoes["ventoinha"]["justificativa"]

    def test_aceita_rotulo_bruto_do_operador(self, cliente: TestClient) -> None:
        """A mesma normalização do cadastro: quem removeu vê o rótulo, não o canônico."""
        _pular_sem_base()
        _cadastrar(cliente, "falta_fase")
        resposta = cliente.delete("/documentos/new_falta_fase_2")
        assert resposta.status_code == 200
        assert resposta.json()["condicao"] == "falta_fase"

    def test_sem_cadastro_e_404(self, cliente: TestClient) -> None:
        resposta = cliente.delete("/documentos/ventoinha")
        assert resposta.status_code == 404
        assert "cadastrado em operação" in resposta.json()["detail"]

    def test_remover_duas_vezes_e_404_na_segunda(self, cliente: TestClient) -> None:
        """A rota não é idempotente de propósito: o segundo 404 diz que algo mudou."""
        _pular_sem_base()
        _cadastrar(cliente, "ventoinha")
        assert cliente.delete("/documentos/ventoinha").status_code == 200
        assert cliente.delete("/documentos/ventoinha").status_code == 404

    def test_remove_cadastro_invisivel_sobre_condicao_mapeada(
        self, cliente: TestClient, registro: RegistroDocumentos
    ) -> None:
        """A linha existe no registro mesmo sem aparecer na cobertura, e a rota a alcança.

        Cadastrar para uma condição que o mapa já cobre grava a associação e não muda o
        roteamento (ADR-014). A interface não marca a linha como *cadastrado
        em operação* e portanto não oferece o botão — mas a API remove.
        """
        _pular_sem_base()
        _cadastrar(cliente, "desalinhado")
        assert registro.documento_de("desalinhado") == "DocOp-desalinhado"

        assert cliente.delete("/documentos/desalinhado").status_code == 200
        assert registro.documento_de("desalinhado") is None

    def test_condicao_do_mapa_e_404_com_motivo_proprio(self, cliente: TestClient) -> None:
        """A base entregue é versionada em código e não se altera pela API (ADR-014).

        O motivo precisa citar o documento que atende a condição: um 404 genérico faria o
        integrador concluir que `desalinhado` não existe.
        """
        resposta = cliente.delete("/documentos/desalinhado")
        assert resposta.status_code == 404
        assert "Doc2" in resposta.json()["detail"]

    def test_estado_operacional_e_422(self, cliente: TestClient) -> None:
        resposta = cliente.delete("/documentos/normal")
        assert resposta.status_code == 422
        assert "estado operacional" in resposta.json()["detail"]

    def test_condicao_inexistente_e_422(self, cliente: TestClient) -> None:
        resposta = cliente.delete("/documentos/cavitacao")
        assert resposta.status_code == 422
