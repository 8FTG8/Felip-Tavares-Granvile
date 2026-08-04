/** Conversa com o assistente técnico. */

import { useEffect, useRef, useState } from "react";
import { ApiIndisponivel, RequisicaoRecusada, api } from "../api/cliente";
import type { TurnoConversa } from "../api/cliente";
import type { EstadoSistema, RoteamentoFluxo } from "../api/tipos";
import { AvisoApi, Botao, Campo, Cartao, Entrada, Etiqueta, Icone, Selecao, Vazio } from "../componentes/base";
import { Prosa, SeloCaminho } from "../componentes/dominio";
import { Topo } from "../componentes/navegacao";

const CONDICOES = [
  "cocked_rotor",
  "rolamento_inner",
  "rolamento_outer",
  "rolamento_ball",
  "rolamento_combination",
  "desalinhado",
  "desbalanceado",
  "correia",
  "polia",
  "eccentric_rotor",
  "ventoinha",
  "falta_fase",
];

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
  const fim = useRef<HTMLDivElement>(null);
  const cancelamento = useRef<AbortController | null>(null);

  // `block: "nearest"` mantém a rolagem dentro do painel da conversa. Com o comportamento
  // suave e o padrão do navegador, cada token faria a página inteira saltar durante os
  // trinta segundos de geração.
  useEffect(() => {
    fim.current?.scrollIntoView({ block: "nearest" });
  }, [conversa, parcial]);

  // Sair da tela durante a geração precisa interromper a leitura do fluxo: sem isso, ela
  // segue escrevendo em um componente desmontado.
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
    // O roteamento do turno anterior não pode continuar exibido enquanto o novo é gerado:
    // é justamente o selo que sustenta a tese anti-alucinação.
    setRoteamento(null);

    // O fluxo entrega o texto acumulado a cada parte. Guardá-lo em uma variável local,
    // em vez de ler o estado ao final, evita depender do agendamento assíncrono do React.
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

      // A pergunta permanece na tela e o erro vira uma fala: apagá-la em silêncio faria a
      // falha parecer um botão que não funciona.
      if (falha instanceof ApiIndisponivel) setApiFora(true);
      const motivo =
        falha instanceof RequisicaoRecusada
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
        etiquetas={sistema && <Etiqueta cor="var(--color-acento)">{sistema.modelo}</Etiqueta>}
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

      <div className="grid grid-cols-[3fr_1fr] gap-4 items-start">
        <div>
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
                opcoes={CONDICOES.map((item) => ({ valor: item, rotulo: item }))}
              />
            </Campo>
          </Cartao>

          {apiFora && <AvisoApi />}

          <Cartao semPadding className="overflow-hidden">
            <div className="max-h-[460px] overflow-y-auto p-5">
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
              <Botao variante="primario" icone="send" onClick={() => enviar(pergunta)} disabled={gerando}>
                Enviar
              </Botao>
            </div>
          </Cartao>
        </div>

        <div className="space-y-4">
          <Cartao titulo="Contexto">
            <Dado rotulo="Condição" valor={condicao} />
            <Dado rotulo="Procedimento" valor={roteamento?.documento || "—"} />

            {roteamento?.caminho && (
              <div className="mt-3">
                <SeloCaminho caminho={roteamento.caminho} compacto />
              </div>
            )}

            {roteamento?.fontes?.length ? (
              <div className="mt-3">
                <p className="text-[0.7rem] uppercase tracking-wide text-tinta-suave mb-1">
                  Seções citadas
                </p>
                {roteamento.fontes.map((fonte) => (
                  <p
                    key={fonte}
                    className="text-[0.78rem] text-tinta-secundaria py-1 border-b border-borda last:border-0"
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
                className="w-full text-left text-[0.81rem] text-tinta-secundaria bg-fundo hover:bg-ativo rounded-lg px-3 py-2 mb-1.5 transition disabled:opacity-50"
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

function Balao({ fala, digitando }: { fala: Fala; digitando?: boolean }) {
  const doUsuario = fala.papel === "usuario";
  return (
    <div className={`flex gap-3 mb-4 ${doUsuario ? "flex-row-reverse" : ""}`}>
      <span
        className={`flex items-center justify-center w-8 h-8 rounded-full shrink-0 ${
          doUsuario ? "bg-ativo text-tinta-secundaria" : "bg-acento-suave text-acento"
        }`}
      >
        <Icone nome={doUsuario ? "person" : "settings_suggest"} tamanho={17} />
      </span>

      <div
        aria-live={digitando ? "polite" : undefined}
        className={`max-w-[80%] rounded-xl px-4 py-3 ${
          doUsuario
            ? "bg-ativo"
            : fala.erro
              ? "bg-critico-suave border border-critico/30"
              : "bg-superficie border border-borda"
        }`}
      >
        {digitando ? (
          <span className="flex gap-1 py-1">
            {[0, 150, 300].map((atraso) => (
              <span
                key={atraso}
                className="w-1.5 h-1.5 rounded-full bg-tinta-suave animate-bounce"
                style={{ animationDelay: `${atraso}ms` }}
              />
            ))}
          </span>
        ) : doUsuario ? (
          <p className="text-[0.88rem] text-tinta">{fala.conteudo}</p>
        ) : fala.erro ? (
          <p className="text-[0.86rem] text-critico">{fala.conteudo}</p>
        ) : (
          <>
            <Prosa texto={fala.conteudo} />
            {fala.fontes?.length ? (
              <p className="text-[0.72rem] text-tinta-suave mt-2 pt-2 border-t border-borda">
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
function Dado({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="mb-3 last:mb-0">
      <p className="text-[0.7rem] uppercase tracking-wide text-tinta-suave">{rotulo}</p>
      <p className="text-[0.9rem] font-semibold text-tinta">{valor}</p>
    </div>
  );
}
