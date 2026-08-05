/** Conversa com o assistente técnico. */

import { useEffect, useRef, useState } from "react";
import {
  ApiIndisponivel,
  ModeloIndisponivel,
  RequisicaoRecusada,
  api,
} from "../api/cliente";
import type { TurnoConversa } from "../api/cliente";
import type { EstadoSistema, RoteamentoFluxo } from "../api/tipos";
import {
  AvisoApi,
  AvisoModelo,
  Botao,
  Campo,
  Cartao,
  Entrada,
  Etiqueta,
  Icone,
  Selecao,
  Vazio,
} from "../componentes/base";
import { DEFEITOS_ORDENADOS, nomeCondicao } from "../condicoes";
import { COR, atrasosDigitacao } from "../estilo";
import { useDecorrido } from "../tempo";
import { Prosa, SeloCaminho } from "../componentes/dominio";
import { Topo } from "../componentes/navegacao";

/**
 * As doze famílias de defeito, ordenadas pelo nome em português.
 *
 * A lista vinha escrita à mão em ordem arbitrária e com os identificadores de banco como
 * rótulo. Agora vem do vocabulário, que é a mesma fonte usada nas outras telas.
 */
const CONDICOES = DEFEITOS_ORDENADOS;

const SUGESTOES: Record<string, string[]> = {
  cocked_rotor: ["o eixo pode estar empenado?", "como diferencio de desbalanceamento?"],
  rolamento_inner: ["falta lubrificação?", "como substituo o rolamento?"],
  desalinhado: ["como alinho?", "o que é pé manco?"],
  desbalanceado: ["preciso balancear?", "como calculo a massa de correção?"],
  correia: ["a correia está frouxa?"],
  polia: ["a polia está gasta?"],
  falta_fase: ["como corrijo?"],
  eccentric_rotor: ["como corrijo?"],
  ventoinha: ["como corrijo?"],
};

interface Fala extends TurnoConversa {
  fontes?: string[];
  erro?: boolean;
}

export function Assistente({ sistema }: { sistema: EstadoSistema | null }) {
  const [condicao, setCondicao] = useState(CONDICOES[0]);
  const [conversa, setConversa] = useState<Fala[]>([]);
  const [pergunta, setPergunta] = useState("");
  const [parcial, setParcial] = useState("");
  const [gerando, setGerando] = useState(false);
  const [roteamento, setRoteamento] = useState<RoteamentoFluxo | null>(null);
  const [apiFora, setApiFora] = useState(false);
  const [modeloFora, setModeloFora] = useState<string | null>(null);
  const segundos = useDecorrido(gerando);
  const fim = useRef<HTMLDivElement>(null);
  const cancelamento = useRef<AbortController | null>(null);

  // `block: "nearest"` mantém a rolagem dentro do painel da conversa. Com o
  // comportamento suave e o padrão do navegador, cada token faria a página inteira
  // saltar durante os trinta segundos de geração.
  useEffect(() => {
    fim.current?.scrollIntoView({ block: "nearest" });
  }, [conversa, parcial]);

  // Sair da tela durante a geração precisa interromper a leitura do fluxo: sem isso,
  // ela segue escrevendo em um componente desmontado.
  useEffect(() => () => cancelamento.current?.abort(), []);

  async function enviar(texto: string) {
    const conteudo = texto.trim();
    if (!conteudo || gerando) return;

    const historico: TurnoConversa[] = conversa.map(({ papel, conteudo }) => ({
      papel,
      conteudo,
    }));

    setConversa((atual) => [...atual, { papel: "usuario", conteudo }]);
    setPergunta("");
    setParcial("");
    setGerando(true);
    setApiFora(false);
    setModeloFora(null);
    // O roteamento do turno anterior não pode continuar exibido enquanto o novo é
    // gerado: é justamente o selo que sustenta a tese anti-alucinação.
    setRoteamento(null);

    // O fluxo entrega o texto acumulado a cada parte. Guardá-lo em uma variável
    // local, em vez de ler o estado ao final, evita depender do agendamento
    // assíncrono do React.
    let completo = "";

    const controlador = new AbortController();
    cancelamento.current = controlador;

    try {
      const rota = await api.conversarEmFluxo(
        conteudo,
        condicao,
        historico,
        (texto) => {
          completo = texto;
          setParcial(texto);
        },
        controlador.signal,
      );
      setRoteamento(rota);
      setConversa((atual) => [
        ...atual,
        { papel: "assistente", conteudo: completo, fontes: rota.fontes },
      ]);
    } catch (falha) {
      if (controlador.signal.aborted) return;

      // A pergunta permanece na tela e o erro vira uma fala: apagá-la em silêncio
      // faria a falha parecer um botão que não funciona.
      if (falha instanceof ApiIndisponivel) setApiFora(true);
      if (falha instanceof ModeloIndisponivel) setModeloFora(falha.message);
      const motivo =
        falha instanceof ModeloIndisponivel
          ? falha.message
          : falha instanceof RequisicaoRecusada
            ? falha.message
            : falha instanceof ApiIndisponivel
              ? "A API não respondeu. Verifique se o serviço está no ar."
              : `Falha ao gerar a resposta: ${String(falha)}`;
      setConversa((atual) => [...atual, { papel: "assistente", conteudo: motivo, erro: true }]);
    } finally {
      cancelamento.current = null;
      setGerando(false);
      setParcial("");
    }
  }

  return (
    <>
      <Topo
        titulo="Assistente técnico"
        descricao="As respostas vêm exclusivamente dos procedimentos da empresa. Sem procedimento que a fundamente, o assistente diz isso em vez de improvisar."
        etiquetas={sistema && <Etiqueta cor={COR.acento}>{sistema.modelo}</Etiqueta>}
        acao={
          <Botao
            icone="restart_alt"
            onClick={() => {
              setConversa([]);
              setRoteamento(null);
            }}
          >
            Limpar conversa
          </Botao>
        }
      />

      {/* O trilho de contexto vem **antes** da conversa quando as colunas empilham:
          é ele que diz qual procedimento respondeu, e empurrá-lo para depois de uma
          conversa longa o deixaria fora da tela justamente na hora de conferir. */}
      <div className="grid grid-cols-1 xl:grid-cols-[3fr_1fr] gap-4 items-start">
        <div className="order-2 xl:order-1">
          <Cartao className="mb-4">
            <Campo
              id="condicao-chat"
              rotulo="Condição do equipamento"
              auxilio="A condição define qual procedimento responde. Sem ela, o assistente teria de escolher um documento por conta própria."
            >
              <Selecao
                id="condicao-chat"
                valor={condicao}
                aoMudar={(valor) => {
                  setCondicao(valor);
                  setRoteamento(null);
                }}
                // O identificador acompanha o nome, e não o substitui: é ele que
                // aparece no JSON do sensor e na citação da fonte.
                opcoes={CONDICOES.map((item) => ({
                  valor: item,
                  rotulo: `${nomeCondicao(item)} · ${item}`,
                }))}
              />
            </Campo>
          </Cartao>

          {apiFora && <AvisoApi />}
          {/* Antecipa a falha em vez de esperar o usuário topar com ela: o estado do
              modelo já chega em `GET /sistema`, e a informação estava sendo publicada
              e ignorada. */}
          {!apiFora && (modeloFora || sistema?.modelo_disponivel === false) && (
            <AvisoModelo detalhe={modeloFora ?? undefined} />
          )}

          <Cartao semPadding className="overflow-hidden">
            <div className="max-h-[var(--altura-conversa)] overflow-y-auto p-4 sm:p-5">
              {conversa.length === 0 && !gerando && (
                <Vazio
                  icone="forum"
                  titulo="Pergunte sobre a falha"
                  descricao="As orientações citam a seção do procedimento que as sustenta."
                />
              )}

              {conversa.map((fala, indice) => (
                <Balao key={indice} fala={fala} />
              ))}

              {gerando && (
                <Balao
                  fala={{ papel: "assistente", conteudo: parcial || "…" }}
                  digitando={!parcial}
                  segundos={segundos}
                />
              )}

              <div ref={fim} />
            </div>

            <div className="border-t border-borda p-3 flex gap-2">
              <label htmlFor="pergunta-chat" className="sr-only">
                Pergunta ao assistente
              </label>
              <Entrada
                id="pergunta-chat"
                valor={pergunta}
                aoMudar={setPergunta}
                aoTeclar={(tecla) => tecla === "Enter" && enviar(pergunta)}
                placeholder="Pergunte sobre a falha…"
                desabilitado={gerando}
                className="flex-1"
              />
              <Botao
                variante="primario"
                icone="send"
                onClick={() => enviar(pergunta)}
                disabled={gerando}
              >
                <span className="hidden sm:inline">Enviar</span>
              </Botao>
            </div>
          </Cartao>
        </div>

        <div className="order-1 xl:order-2 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-1 gap-4">
          <Cartao titulo="Contexto">
            <Dado rotulo="Condição" valor={nomeCondicao(condicao)} detalhe={condicao} />
            <Dado rotulo="Procedimento" valor={roteamento?.documento || "—"} />

            {roteamento?.caminho && (
              <div className="mt-3">
                <SeloCaminho caminho={roteamento.caminho} compacto />
              </div>
            )}

            {roteamento?.fontes?.length ? (
              <div className="mt-3">
                <p className="rotulo text-tinta-suave mb-1">
                  Seções citadas
                </p>
                {roteamento.fontes.map((fonte) => (
                  <p
                    key={fonte}
                    className="text-nota text-tinta-secundaria py-1 border-b border-borda last:border-0"
                  >
                    {fonte}
                  </p>
                ))}
              </div>
            ) : null}
          </Cartao>

          <Cartao titulo="Sugestões">
            {(SUGESTOES[condicao] ?? ["como corrijo?"]).map((sugestao) => (
              <button
                key={sugestao}
                onClick={() => enviar(sugestao)}
                disabled={gerando}
                className="foco w-full text-left text-nota text-tinta-secundaria bg-fundo hover:bg-ativo rounded-controle px-3 py-2 mb-1.5 transition disabled:opacity-45"
              >
                {sugestao}
              </button>
            ))}
          </Cartao>
        </div>
      </div>
    </>
  );
}

function Balao({
  fala,
  digitando,
  segundos = 0,
}: {
  fala: Fala;
  digitando?: boolean;
  /** Tempo decorrido, exibido enquanto o modelo ainda não emitiu o primeiro token. */
  segundos?: number;
}) {
  const doUsuario = fala.papel === "usuario";

  return (
    <div className={`flex gap-3 mb-4 ${doUsuario ? "flex-row-reverse" : ""}`}>
      <span
        className={`flex items-center justify-center w-8 h-8 rounded-full shrink-0 ${
          doUsuario ? "bg-ativo text-tinta-secundaria" : "bg-acento-suave text-acento"
        }`}
      >
        <Icone nome={doUsuario ? "person" : "settings_suggest"} tamanho="pequeno" />
      </span>

      <div
        aria-live={digitando ? "polite" : undefined}
        className={`max-w-[85%] rounded-cartao px-4 py-3 ${
          doUsuario
            ? "bg-ativo"
            : fala.erro
              ? "bg-critico-suave border border-critico/25"
              : "bg-superficie border border-borda"
        }`}
      >
        {digitando ? (
          /* Os pontinhos sozinhos não distinguem "gerando há dois segundos" de
             "travou": em estação sem GPU dedicada a primeira resposta leva dezenas de
             segundos, e numa sala as duas situações se parecem exatamente igual. */
          <div>
            <span className="flex items-center gap-1 py-1">
              {atrasosDigitacao().map((atraso) => (
                <span
                  key={atraso}
                  className="w-1.5 h-1.5 rounded-full bg-tinta-suave animate-bounce"
                  style={{ animationDelay: `${atraso}ms` }}
                />
              ))}
              {segundos > 0 && (
                <span className="tabular text-nota text-tinta-suave ml-2">{segundos}s</span>
              )}
            </span>
            {segundos >= 8 && (
              <p className="text-nota text-tinta-suave mt-1">
                Redigindo a partir dos trechos recuperados. Sem GPU dedicada, leva dezenas
                de segundos.
              </p>
            )}
          </div>
        ) : doUsuario ? (
          <p className="text-corpo text-tinta">{fala.conteudo}</p>
        ) : fala.erro ? (
          <p className="text-corpo text-critico">{fala.conteudo}</p>
        ) : (
          <>
            <Prosa texto={fala.conteudo} />
            {fala.fontes?.length ? (
              <p className="text-nota text-tinta-suave mt-2 pt-2 border-t border-borda">
                Fontes: {fala.fontes.join(" · ")}
              </p>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

/** Par rótulo/valor do trilho de contexto — apresentação, não campo de formulário. */
function Dado({
  rotulo,
  valor,
  detalhe,
}: {
  rotulo: string;
  valor: string;
  detalhe?: string;
}) {
  return (
    <div className="mb-3 last:mb-0">
      <p className="rotulo text-tinta-suave">{rotulo}</p>
      <p className="text-corpo-forte text-tinta break-words">{valor}</p>
      {detalhe && <code className="text-nota text-tinta-suave break-all">{detalhe}</code>}
    </div>
  );
}
