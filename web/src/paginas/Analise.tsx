/**
 * Análise de um evento de sensor.
 *
 * Entrada à esquerda, resultado à direita: trocando o caso, a resposta muda sem que a
 * página se reorganize, e os quatro caminhos ficam comparáveis. Abaixo de 1280px as
 * colunas empilham, entrada em cima.
 */

import { useState } from "react";
import { Bar, BarChart, Tooltip, XAxis } from "recharts";
import {
  ApiIndisponivel,
  ModeloIndisponivel,
  api,
  RequisicaoRecusada,
} from "../api/cliente";
import type {
  AnaliseEvento,
  ContextoHistorico,
  EstadoSistema,
  EventoSensor,
} from "../api/tipos";
import { Moldura } from "../componentes/graficos";
import {
  AvisoApi,
  AvisoModelo,
  Botao,
  Campo,
  Cartao,
  Carregando,
  Dica,
  Entrada,
  Etiqueta,
  Segmentado,
  Vazio,
} from "../componentes/base";
import { numero } from "../formato";
import {
  COR,
  CURSOR,
  MARGEM,
  espacoMarcacao,
  marcacao,
  raioBarra,
} from "../estilo";
import {
  ChamadaCadastro,
  Fontes,
  Prosa,
  RodapeModelo,
  SeloCaminho,
} from "../componentes/dominio";
import { nomeCondicao } from "../condicoes";
import { Topo } from "../componentes/navegacao";

/** Evento do enunciado, ponto de partida da demonstração. */
const EVENTO_EXEMPLO: EventoSensor = {
  id: 114387,
  created_at: "2026-06-01 21:32:53.911176+00:00",
  z_rms_velocity_mm_s: 1.517,
  x_rms_velocity_mm_s: 2.0,
  temperature_c: 24.69,
  z_peak_acceleration_g: 0.484,
  x_peak_acceleration_g: 0.631,
  z_peak_vel_comp_freq_hz: 61.0,
  x_peak_vel_comp_freq_hz: 61.0,
  z_rms_acceleration_g: 0.09,
  x_rms_acceleration_g: 0.114,
  z_kurtosis: 2.392,
  x_kurtosis: 2.77,
  z_crest_factor: 3.747,
  x_crest_factor: 4.269,
  z_high_freq_rms_accel_g: 0.129,
  x_high_freq_rms_accel_g: 0.147,
  fault: "cocked_rotor_2",
  rpm: 1000.0,
};

/**
 * Um caso por caminho de resposta (ADR-006), na ordem da demonstração. O rótulo nomeia
 * o defeito e a descrição, o cenário; nenhum dos dois antecipa o caminho que o sistema
 * vai escolher, e os botões são neutros pelo mesmo motivo.
 */
const CASOS = [
  {
    fault: "cocked_rotor_2",
    rotulo: nomeCondicao("cocked_rotor"),
    descricao: "Defeito com procedimento cadastrado",
  },
  {
    fault: "new_falta_fase_0",
    rotulo: nomeCondicao("falta_fase"),
    descricao: "Defeito sem procedimento algum",
  },
  {
    fault: "eccentric_rotor_2",
    rotulo: nomeCondicao("eccentric_rotor"),
    descricao: "Documentação apenas adjacente",
  },
  {
    fault: "normal_2",
    rotulo: nomeCondicao("normal"),
    descricao: "Estado operacional, não falha",
  },
];

export function Analise({
  sistema,
  aoCadastrar,
}: {
  sistema: EstadoSistema | null;
  /** Leva ao cadastro com a condição recusada já selecionada. */
  aoCadastrar: (condicao: string) => void;
}) {
  const [caso, setCaso] = useState(0);
  const [json, setJson] = useState(
    JSON.stringify({ ...EVENTO_EXEMPLO, fault: CASOS[0].fault }, null, 2),
  );
  const [pergunta, setPergunta] = useState("");
  const [jsonAberto, setJsonAberto] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [resultado, setResultado] = useState<AnaliseEvento | null>(null);
  // Conta os resultados da sessão: as fontes vêm abertas apenas no primeiro.
  const [quantos, setQuantos] = useState(0);
  const [erro, setErro] = useState<string | null>(null);
  const [apiFora, setApiFora] = useState(false);
  const [modeloFora, setModeloFora] = useState<string | null>(null);

  function trocarCaso(indice: number) {
    setCaso(indice);
    setJson(JSON.stringify({ ...EVENTO_EXEMPLO, fault: CASOS[indice].fault }, null, 2));
    setResultado(null);
    setErro(null);
  }

  async function analisar() {
    setErro(null);
    setApiFora(false);
    setModeloFora(null);

    let evento: EventoSensor;
    try {
      evento = JSON.parse(json) as EventoSensor;
    } catch (falha) {
      setErro(`JSON inválido: ${String(falha)}`);
      return;
    }

    setCarregando(true);
    try {
      setResultado(await api.analisar(evento, pergunta || undefined));
      setQuantos((n) => n + 1);
    } catch (falha) {
      if (falha instanceof ModeloIndisponivel) setModeloFora(falha.message);
      else if (falha instanceof ApiIndisponivel) setApiFora(true);
      else if (falha instanceof RequisicaoRecusada) setErro(falha.message);
      else setErro(String(falha));
      setResultado(null);
    } finally {
      setCarregando(false);
    }
  }

  return (
    <>
      <Topo
        titulo="Análise de evento"
        descricao="Localiza ocorrências semelhantes no histórico e prescreve a ação corretiva quando há procedimento que a fundamente."
        etiquetas={
          sistema && (
            <>
              <Etiqueta cor={COR.acento}>{sistema.modelo}</Etiqueta>
              <Etiqueta>limiar {sistema.limiar_relevancia.toFixed(3)}</Etiqueta>
            </>
          )
        }
      />

      {/* Os quatro casos ficam visíveis o tempo todo: num menu suspenso, o fato de os
          caminhos formarem um conjunto fechado e exaustivo se perderia. */}
      <Cartao titulo="Casos de demonstração" complemento="um por caminho de resposta" className="mb-4">
        <Segmentado
          rotulo="Caso de demonstração"
          valor={caso}
          aoMudar={trocarCaso}
          opcoes={CASOS.map((item, indice) => ({
            valor: indice,
            rotulo: item.rotulo,
            descricao: item.descricao,
          }))}
        />
      </Cartao>

      <div className="grid grid-cols-1 xl:grid-cols-[2fr_3fr] gap-4 items-start">
        <Cartao titulo="Evento de entrada">
          <button
            onClick={() => setJsonAberto(!jsonAberto)}
            aria-expanded={jsonAberto}
            aria-controls="json-evento"
            className="foco w-full flex items-center gap-2 text-nota text-tinta-secundaria border border-borda rounded-controle px-3 py-2 hover:bg-fundo transition"
          >
            JSON enviado à API
            <span aria-hidden="true" className="ml-auto text-tinta-suave">
              {jsonAberto ? "−" : "+"}
            </span>
          </button>
          {jsonAberto && (
            <textarea
              id="json-evento"
              aria-label="JSON do evento enviado à API"
              value={json}
              onChange={(evento) => setJson(evento.target.value)}
              spellCheck={false}
              className="foco w-full mt-2 h-[var(--altura-json)] text-nota font-mono bg-superficie text-tinta border border-borda rounded-controle p-3 transition focus:border-acento"
            />
          )}

          <Campo id="pergunta-analise" rotulo="Pergunta específica (opcional)" className="mt-4">
            <Entrada
              id="pergunta-analise"
              valor={pergunta}
              aoMudar={setPergunta}
              placeholder="ex.: o eixo pode estar empenado?"
            />
          </Campo>

          <Botao
            variante="primario"
            icone="play_arrow"
            onClick={analisar}
            disabled={carregando}
            className="w-full mt-4"
          >
            {carregando ? "Analisando…" : "Analisar evento"}
          </Botao>
        </Cartao>

        <div>
          {apiFora ? (
            <AvisoApi />
          ) : modeloFora ? (
            <AvisoModelo detalhe={modeloFora} />
          ) : erro ? (
            <Cartao className="border-critico/25">
              <p role="alert" className="text-corpo text-critico">
                {erro}
              </p>
            </Cartao>
          ) : carregando ? (
            <Cartao>
              <Carregando texto="Consultando histórico e procedimentos…" contarTempo />
            </Cartao>
          ) : resultado ? (
            <Resultado
              key={quantos}
              resultado={resultado}
              primeiro={quantos === 1}
              aoCadastrar={aoCadastrar}
            />
          ) : (
            <Cartao>
              <Vazio
                icone="vital_signs"
                titulo="Escolha um caso e acione Analisar evento"
                descricao="A recomendação aparece aqui, com as seções de procedimento que a fundamentam."
              />
            </Cartao>
          )}
        </div>
      </div>

      {resultado?.contexto && <Contexto contexto={resultado.contexto} />}
    </>
  );
}

function Resultado({
  resultado,
  primeiro,
  aoCadastrar,
}: {
  resultado: AnaliseEvento;
  primeiro: boolean;
  aoCadastrar: (condicao: string) => void;
}) {
  return (
    <Cartao>
      <SeloCaminho caminho={resultado.caminho} documento={resultado.documento} />
      <p className="text-nota text-tinta-secundaria my-3">
        Condição identificada:{" "}
        <strong className="text-tinta">{nomeCondicao(resultado.condicao)}</strong>{" "}
        <code>{resultado.condicao}</code> · anotada pelo operador como{" "}
        <code>{resultado.rotulo_bruto}</code>
      </p>
      <Prosa texto={resultado.recomendacao} />

      {resultado.caminho === "sem_documento" && (
        <ChamadaCadastro condicao={resultado.condicao} aoCadastrar={aoCadastrar} />
      )}

      <Fontes fontes={resultado.fontes} inicialmenteAberto={primeiro} />
      <RodapeModelo modelo={resultado.modelo} />
    </Cartao>
  );
}

function Contexto({ contexto }: { contexto: ContextoHistorico }) {
  const serie = Object.entries(contexto.distribuicao_temporal)
    .map(([dia, eventos]) => ({ dia, eventos }))
    .sort((a, b) => a.dia.localeCompare(b.dia));
  const raio = raioBarra();

  return (
    <Cartao
      titulo="Ocorrências semelhantes no histórico"
      complemento={`${numero(contexto.total_ocorrencias_similares)} eventos`}
      className="mt-4"
    >
      <div className="grid grid-cols-1 xl:grid-cols-[3fr_2fr] gap-6">
        <div>
          {contexto.ocorrencias_por_condicao.map((ocorrencia) => (
            <div key={ocorrencia.condicao} className="py-2 border-b border-borda last:border-0">
              <div className="flex flex-wrap items-center gap-x-2">
                <span className="text-corpo font-semibold text-tinta">
                  {nomeCondicao(ocorrencia.condicao)}
                </span>
                <span className="text-nota text-tinta-suave">
                  {ocorrencia.vizinhos} de {contexto.vizinhos.length} vizinhos
                </span>
                <span className="ml-auto text-nota text-tinta-secundaria">
                  {numero(ocorrencia.ocorrencias_historicas)} no histórico ·{" "}
                  {ocorrencia.frequencia_diaria.toFixed(0)}/dia
                </span>
              </div>
              <div className="h-1 rounded-full bg-ativo mt-1.5 overflow-hidden">
                <div
                  className="h-full bg-acento rounded-full"
                  style={{
                    width: `${(ocorrencia.vizinhos / contexto.vizinhos.length) * 100}%`,
                  }}
                />
              </div>
            </div>
          ))}

          {contexto.ocorrencias_por_condicao.length > 1 && (
            <div className="mt-4 bg-fundo border-l-4 border-acento rounded-sutil p-3 text-nota text-tinta-secundaria">
              <strong className="text-tinta">
                Os vizinhos mais próximos pertencem a famílias diferentes.
              </strong>{" "}
              A assinatura vibratória agregada não separa esses modos de falha — distingui-los
              exigiria análise espectral de envelope, que estas métricas não trazem. É por isso
              que o sistema usa o rótulo anotado pelo operador em vez de inferir o defeito a
              partir dos sensores.
            </div>
          )}
        </div>

        <div>
          <Moldura altura="baixo">
            <BarChart data={serie} margin={MARGEM.compacto}>
              <XAxis
                dataKey="dia"
                tickLine={false}
                axisLine={{ stroke: COR.borda }}
                tick={marcacao()}
                tickFormatter={(dia: string) => dia.slice(8, 10) + "/" + dia.slice(5, 7)}
                minTickGap={espacoMarcacao()}
              />
              <Tooltip content={<Dica />} cursor={CURSOR} />
              <Bar dataKey="eventos" fill={COR.acento} radius={[raio, raio, 0, 0]} />
            </BarChart>
          </Moldura>
          <p className="text-nota text-tinta-suave mt-1">
            Distribuição ao longo do tempo das condições presentes na vizinhança.
          </p>
        </div>
      </div>

      <details className="mt-4">
        <summary className="foco cursor-pointer text-nota font-medium text-tinta-secundaria">
          Vizinhos individuais ({contexto.vizinhos.length})
        </summary>
        <div className="overflow-x-auto border border-borda rounded-controle mt-2">
          <table className="tabular w-full text-nota">
            <thead>
              <tr className="bg-fundo text-tinta-suave rotulo">
                <th className="text-left font-semibold px-3 py-2">ID</th>
                <th className="text-left font-semibold px-3 py-2">Registrado em</th>
                <th className="text-left font-semibold px-3 py-2">Condição</th>
                <th className="text-left font-semibold px-3 py-2">Anotação do operador</th>
                <th className="text-right font-semibold px-3 py-2">rpm</th>
                <th className="text-right font-semibold px-3 py-2">Similaridade</th>
              </tr>
            </thead>
            <tbody>
              {contexto.vizinhos.map((vizinho) => (
                <tr key={vizinho.id} className="border-t border-borda">
                  <td className="px-3 py-1.5 text-tinta-secundaria">{vizinho.id}</td>
                  <td className="px-3 py-1.5 text-tinta-secundaria whitespace-nowrap">
                    {new Date(vizinho.created_at).toLocaleString("pt-BR")}
                  </td>
                  <td className="px-3 py-1.5 font-medium text-tinta whitespace-nowrap">
                    {nomeCondicao(vizinho.condicao)}
                  </td>
                  <td className="px-3 py-1.5 text-tinta-secundaria">
                    <code className="text-nota">{vizinho.rotulo_bruto}</code>
                  </td>
                  <td className="px-3 py-1.5 text-right text-tinta-secundaria">
                    {vizinho.rpm.toFixed(0)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-tinta-secundaria">
                    {vizinho.similaridade.toFixed(3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Cartao>
  );
}
