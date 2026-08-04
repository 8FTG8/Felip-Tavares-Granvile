/**
 * Análise de um evento de sensor.
 *
 * Entrada à esquerda, resultado à direita. O arranjo serve à demonstração: trocando o
 * caso, a resposta muda sem que a página se reorganize, e os quatro caminhos ficam
 * comparáveis lado a lado.
 */

import { useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { ApiIndisponivel, api, RequisicaoRecusada } from "../api/cliente";
import type { AnaliseEvento, ContextoHistorico, EstadoSistema } from "../api/tipos";
import {
  AvisoApi,
  Botao,
  Campo,
  Cartao,
  Carregando,
  Dica,
  Entrada,
  Etiqueta,
  Selecao,
  Vazio,
  numero,
} from "../componentes/base";
import { Fontes, Prosa, RodapeModelo, SeloCaminho } from "../componentes/dominio";
import { Topo } from "../componentes/navegacao";

/** Evento do enunciado, ponto de partida da demonstração. */
const EVENTO_EXEMPLO = {
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

/** Um caso por caminho de resposta (ADR-006), na ordem da demonstração. */
const CASOS = [
  { rotulo: "Defeito com procedimento — cocked_rotor", fault: "cocked_rotor_2" },
  { rotulo: "Defeito sem procedimento — falta_fase", fault: "new_falta_fase_0" },
  { rotulo: "Documentação apenas adjacente — eccentric_rotor", fault: "eccentric_rotor_2" },
  { rotulo: "Estado do sistema — normal", fault: "normal_2" },
];

export function Analise({ sistema }: { sistema: EstadoSistema | null }) {
  const [caso, setCaso] = useState(0);
  const [json, setJson] = useState(
    JSON.stringify({ ...EVENTO_EXEMPLO, fault: CASOS[0].fault }, null, 2),
  );
  const [pergunta, setPergunta] = useState("");
  const [jsonAberto, setJsonAberto] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [resultado, setResultado] = useState<AnaliseEvento | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [apiFora, setApiFora] = useState(false);

  function trocarCaso(indice: number) {
    setCaso(indice);
    setJson(JSON.stringify({ ...EVENTO_EXEMPLO, fault: CASOS[indice].fault }, null, 2));
    setResultado(null);
    setErro(null);
  }

  async function analisar() {
    setErro(null);
    setApiFora(false);

    let evento: Record<string, unknown>;
    try {
      evento = JSON.parse(json);
    } catch (falha) {
      setErro(`JSON inválido: ${String(falha)}`);
      return;
    }

    setCarregando(true);
    try {
      setResultado(await api.analisar(evento, pergunta || undefined));
    } catch (falha) {
      if (falha instanceof ApiIndisponivel) setApiFora(true);
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
              <Etiqueta cor="var(--color-acento)">{sistema.modelo}</Etiqueta>
              <Etiqueta>limiar {sistema.limiar_relevancia.toFixed(3)}</Etiqueta>
            </>
          )
        }
      />

      <div className="grid grid-cols-[2fr_3fr] gap-4 items-start">
        <Cartao titulo="Evento de entrada">
          <Campo id="caso-demo" rotulo="Caso de demonstração" className="mb-4">
            <Selecao
              id="caso-demo"
              valor={caso}
              aoMudar={(valor) => trocarCaso(Number(valor))}
              opcoes={CASOS.map((item, indice) => ({ valor: indice, rotulo: item.rotulo }))}
            />
          </Campo>

          <button
            onClick={() => setJsonAberto(!jsonAberto)}
            aria-expanded={jsonAberto}
            aria-controls="json-evento"
            className="w-full flex items-center gap-2 text-[0.8rem] text-tinta-secundaria border border-borda rounded-lg px-3 py-2 hover:bg-fundo transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-acento/40"
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
              rows={14}
              spellCheck={false}
              className="w-full mt-2 text-[0.76rem] font-mono bg-superficie text-tinta border border-borda rounded-lg p-3 transition focus:border-acento focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-acento/40"
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
          ) : erro ? (
            <Cartao className="border-critico/40">
              <p role="alert" className="text-[0.88rem] text-critico">
                {erro}
              </p>
            </Cartao>
          ) : carregando ? (
            <Cartao>
              <Carregando texto="Consultando histórico e procedimentos…" />
            </Cartao>
          ) : resultado ? (
            <Resultado resultado={resultado} />
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

function Resultado({ resultado }: { resultado: AnaliseEvento }) {
  return (
    <Cartao>
      <SeloCaminho caminho={resultado.caminho} documento={resultado.documento} />
      <p className="text-[0.8rem] text-tinta-secundaria my-3">
        Condição identificada: <strong className="text-tinta">{resultado.condicao}</strong> ·
        anotada pelo operador como <code>{resultado.rotulo_bruto}</code>
      </p>
      <Prosa texto={resultado.recomendacao} />
      <Fontes fontes={resultado.fontes} />
      <RodapeModelo modelo={resultado.modelo} />
    </Cartao>
  );
}

function Contexto({ contexto }: { contexto: ContextoHistorico }) {
  const serie = Object.entries(contexto.distribuicao_temporal)
    .map(([dia, eventos]) => ({ dia, eventos }))
    .sort((a, b) => a.dia.localeCompare(b.dia));

  return (
    <Cartao
      titulo="Ocorrências semelhantes no histórico"
      complemento={`${numero(contexto.total_ocorrencias_similares)} eventos`}
      className="mt-4"
    >
      <div className="grid grid-cols-[3fr_2fr] gap-6">
        <div>
          {contexto.ocorrencias_por_condicao.map((ocorrencia) => (
            <div key={ocorrencia.condicao} className="py-2 border-b border-borda last:border-0">
              <div className="flex items-center gap-2">
                <span className="text-[0.86rem] font-semibold text-tinta">
                  {ocorrencia.condicao}
                </span>
                <span className="text-[0.74rem] text-tinta-suave">
                  {ocorrencia.vizinhos} de {contexto.vizinhos.length} vizinhos
                </span>
                <span className="ml-auto text-[0.8rem] text-tinta-secundaria">
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
            <div className="mt-4 bg-fundo border-l-[3px] border-acento rounded p-3 text-[0.8rem] text-tinta-secundaria leading-relaxed">
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
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={serie} margin={{ left: -26, right: 4, top: 4 }}>
              <XAxis
                dataKey="dia"
                tickLine={false}
                axisLine={{ stroke: "var(--color-borda)" }}
                tick={{ fontSize: 10, fill: "var(--color-tinta-suave)" }}
                tickFormatter={(dia: string) => dia.slice(8, 10) + "/" + dia.slice(5, 7)}
                minTickGap={16}
              />
              <Tooltip content={<Dica />} cursor={{ fill: "var(--color-grade)" }} />
              <Bar dataKey="eventos" fill="var(--color-acento)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <p className="text-[0.74rem] text-tinta-suave mt-1">
            Distribuição ao longo do tempo das condições presentes na vizinhança.
          </p>
        </div>
      </div>

      <details className="mt-4">
        <summary className="cursor-pointer text-[0.82rem] font-medium text-tinta-secundaria">
          Vizinhos individuais ({contexto.vizinhos.length})
        </summary>
        <div className="overflow-x-auto border border-borda rounded-lg mt-2">
          <table className="w-full text-[0.8rem]">
            <thead>
              <tr className="bg-fundo text-tinta-suave text-[0.7rem] uppercase tracking-wide">
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
                  <td className="px-3 py-1.5 text-tinta-secundaria">
                    {new Date(vizinho.created_at).toLocaleString("pt-BR")}
                  </td>
                  <td className="px-3 py-1.5 font-medium text-tinta">{vizinho.condicao}</td>
                  <td className="px-3 py-1.5 text-tinta-secundaria">
                    <code className="text-[0.74rem]">{vizinho.rotulo_bruto}</code>
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
