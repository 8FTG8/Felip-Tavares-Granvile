/** Cadastro de procedimentos e situação da base documental. */

import { useEffect, useRef, useState } from "react";
import { ApiIndisponivel, api, RequisicaoRecusada } from "../api/cliente";
import type { CoberturaDocumental, DocumentoRegistrado, EstadoSistema } from "../api/tipos";
import {
  AvisoApi,
  Botao,
  Campo,
  Cartao,
  Carregando,
  Etiqueta,
  Icone,
  Pilula,
  Selecao,
  Vazio,
} from "../componentes/base";
import { nomeCondicao } from "../condicoes";
import { Topo } from "../componentes/navegacao";

export function Documentos({
  cobertura,
  sistema,
  aoCadastrar,
  condicaoInicial,
}: {
  cobertura: CoberturaDocumental[];
  sistema: EstadoSistema | null;
  aoCadastrar: () => void;
  /** Condição recusada na análise, quando se chegou aqui por aquele caminho. */
  condicaoInicial: string | null;
}) {
  const [condicao, setCondicao] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [apiFora, setApiFora] = useState(false);
  const [sucesso, setSucesso] = useState<DocumentoRegistrado | null>(null);
  const campoArquivo = useRef<HTMLInputElement>(null);

  // Chegando pela recusa da análise, o campo já abre na condição certa.
  useEffect(() => {
    if (condicaoInicial) setCondicao(condicaoInicial);
  }, [condicaoInicial]);

  const pendentes = cobertura.filter((situacao) => !situacao.documentada);
  const opcoes = pendentes.length ? pendentes : cobertura;
  const escolhida = condicao || opcoes[0]?.condicao || "";

  async function cadastrar() {
    if (!arquivo) return;
    setErro(null);
    setApiFora(false);
    setSucesso(null);
    setEnviando(true);
    try {
      setSucesso(await api.cadastrarDocumento(escolhida, arquivo));
      setArquivo(null);
      // A condição cadastrada sai da lista de pendentes. Sem limpar a seleção, o
      // estado continuaria apontando para ela enquanto o campo já mostra outra — e o
      // próximo envio iria para a condição errada, em silêncio.
      setCondicao("");
      if (campoArquivo.current) campoArquivo.current.value = "";
      aoCadastrar();
    } catch (falha) {
      if (falha instanceof ApiIndisponivel) setApiFora(true);
      else if (falha instanceof RequisicaoRecusada) setErro(falha.message);
      else setErro(String(falha));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <Topo
        titulo="Base documental"
        descricao="Defeito sem procedimento não recebe recomendação. Cadastrar aqui faz o sistema passar a atendê-lo imediatamente, sem reiniciar o serviço."
        etiquetas={
          sistema && (
            <>
              <Etiqueta>
                {sistema.familias_documentadas}/{sistema.familias_totais} famílias
              </Etiqueta>
              <Etiqueta>{sistema.trechos_indexados} seções indexadas</Etiqueta>
            </>
          )
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-[3fr_2fr] gap-4 items-start">
        <Cartao
          titulo="Situação por defeito"
          complemento={
            cobertura.length ? `${pendentes.length} aguardando cadastro` : undefined
          }
        >
          {/* Sem cobertura não há lista — e sem estado próprio o cartão aparecia como
              um retângulo vazio com título, indistinguível de "nenhum defeito existe". */}
          {cobertura.length === 0 && (
            <Vazio
              icone="cloud_off"
              titulo="Situação indisponível"
              descricao="A cobertura documental vem da API. Suba o serviço para ver quais defeitos têm procedimento cadastrado."
            />
          )}
          {cobertura.map((situacao) => (
            <div
              key={situacao.condicao}
              className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-3 py-3 border-b border-borda last:border-0"
            >
              <div className="sm:w-32 shrink-0">
                <Pilula
                  texto={situacao.documentada ? "Coberto" : "Sem procedimento"}
                  tom={situacao.documentada ? "sucesso" : "alerta"}
                />
              </div>
              <div className="min-w-0">
                <p className="text-corpo font-semibold text-tinta">
                  {nomeCondicao(situacao.condicao)}{" "}
                  <code className="font-normal text-nota text-tinta-suave">
                    {situacao.condicao}
                  </code>
                </p>
                {situacao.documentada ? (
                  <p className="text-nota text-tinta-secundaria">
                    <code>{situacao.documento}</code>
                    {situacao.cadastrado_em_operacao && (
                      <span className="text-tinta-suave"> · cadastrado em operação</span>
                    )}
                  </p>
                ) : (
                  <p className="text-nota text-tinta-secundaria">{situacao.justificativa}</p>
                )}
              </div>
            </div>
          ))}
        </Cartao>

        <div>
          {apiFora && <AvisoApi />}

          <Cartao titulo="Cadastrar procedimento">
            <p className="text-nota text-tinta-secundaria mb-4">
              O documento passa pelo mesmo tratamento da base original: extração de texto,
              fatiamento por seção numerada e indexação. PDFs digitalizados são reconhecidos
              por OCR.
            </p>

            <Campo id="condicao-doc" rotulo="Defeito que o procedimento cobre" className="mb-4">
              <Selecao
                id="condicao-doc"
                valor={escolhida}
                aoMudar={setCondicao}
                opcoes={opcoes.map((situacao) => ({
                  valor: situacao.condicao,
                  rotulo: `${nomeCondicao(situacao.condicao)} · ${situacao.condicao}`,
                }))}
              />
            </Campo>

            <label
              htmlFor="arquivo-doc"
              className="block text-nota font-medium text-tinta-secundaria mb-1.5"
            >
              Procedimento técnico (PDF)
            </label>
            {/* `sr-only` em vez de `hidden`: `display:none` removeria o campo da ordem
                de foco, e não haveria como escolher o arquivo pelo teclado. */}
            <label className="flex items-center gap-3 border border-dashed border-borda rounded-controle px-4 py-6 cursor-pointer hover:border-acento hover:bg-fundo transition focus-within:border-acento focus-within:ring-2 focus-within:ring-acento/45">
              <Icone nome="upload_file" className="text-tinta-suave" />
              <span className="text-corpo text-tinta-secundaria break-all">
                {arquivo ? arquivo.name : "Selecionar arquivo PDF"}
              </span>
              <input
                id="arquivo-doc"
                ref={campoArquivo}
                type="file"
                accept="application/pdf"
                className="sr-only"
                onChange={(evento) => setArquivo(evento.target.files?.[0] ?? null)}
              />
            </label>

            <Botao
              variante="primario"
              icone="upload"
              onClick={cadastrar}
              disabled={!arquivo || enviando || !escolhida}
              className="w-full mt-4"
            >
              Cadastrar
            </Botao>

            {enviando && <Carregando texto="Extraindo, fatiando e indexando…" />}

            {erro && (
              <p
                role="alert"
                className="text-corpo text-critico bg-critico-suave border border-critico/25 rounded-controle px-3 py-2 mt-3"
              >
                {erro}
              </p>
            )}

            {sucesso && (
              <div className="mt-4 bg-sucesso-suave border border-sucesso/25 rounded-controle p-3">
                <p className="text-corpo text-tinta">
                  <strong>{sucesso.condicao}</strong> passa a ser atendido por{" "}
                  <code>{sucesso.documento}</code> — {sucesso.trechos} seções indexadas (
                  {sucesso.origem === "ocr" ? "transcrito por OCR" : "texto nativo"}).
                </p>
                <details className="mt-2">
                  <summary className="foco cursor-pointer text-nota text-tinta-secundaria">
                    Seções reconhecidas
                  </summary>
                  <ul className="mt-1 text-nota text-tinta-secundaria list-disc pl-5">
                    {sucesso.secoes.map((secao) => (
                      <li key={secao}>{secao}</li>
                    ))}
                  </ul>
                </details>
                <p className="text-nota text-tinta-secundaria mt-2">
                  Volte à <strong>Análise de evento</strong> e consulte um evento desta
                  condição: a recusa foi substituída por prescrição fundamentada no documento
                  recém-cadastrado.
                </p>
              </div>
            )}
          </Cartao>
        </div>
      </div>
    </>
  );
}
