/** Painel do histórico monitorado. */

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CondicaoNoHistorico, EstadoSistema, PainelHistorico } from "../api/tipos";
import {
  AvisoApi,
  Botao,
  Cartao,
  Carregando,
  Dica,
  Entrada,
  Etiqueta,
  Icone,
  numero,
  percentual,
  percentualCss,
} from "../componentes/base";
import { Topo } from "../componentes/navegacao";
import type { Pagina } from "../componentes/navegacao";

const COR_COBERTO = "var(--color-sucesso)";
const COR_SEM_DOCUMENTO = "var(--color-alerta)";

export function Painel({
  dados,
  sistema,
  carregando,
  apiFora,
  aoNavegar,
}: {
  dados: PainelHistorico | null;
  sistema: EstadoSistema | null;
  carregando: boolean;
  apiFora: boolean;
  aoNavegar: (pagina: Pagina) => void;
}) {
  const [filtro, setFiltro] = useState("");

  if (!dados) {
    return (
      <>
        <Topo titulo="Painel do histórico" descricao="Panorama dos eventos monitorados." />
        {apiFora ? (
          <AvisoApi />
        ) : (
          <Cartao>
            <Carregando
              texto={
                carregando
                  ? "Carregando o histórico e montando os índices…"
                  : "Nenhum dado disponível."
              }
            />
          </Cartao>
        )}
      </>
    );
  }

  const { resumo, condicoes } = dados;
  const defeitos = condicoes.filter((c) => c.tipo_condicao === "defeito");
  const pendentes = defeitos.filter((c) => !c.documentada);

  return (
    <>
      <Topo
        titulo="Painel do histórico"
        descricao="Panorama dos eventos monitorados e da cobertura documental por defeito."
        etiquetas={
          <>
            {sistema && <Etiqueta cor="var(--color-acento)">{sistema.modelo}</Etiqueta>}
            <Etiqueta>
              {resumo.primeiro_evento.slice(0, 10)} — {resumo.ultimo_evento.slice(0, 10)}
            </Etiqueta>
          </>
        }
        acao={
          <Botao variante="primario" icone="vital_signs" onClick={() => aoNavegar("analise")}>
            Analisar evento
          </Botao>
        }
      />

      <div className="grid grid-cols-4 gap-4 mb-4">
        <Indicador icone="database" rotulo="Eventos monitorados" valor={numero(resumo.total_eventos)} />
        <Indicador icone="warning" rotulo="Defeitos" valor={numero(resumo.total_defeitos)} />
        <Indicador icone="category" rotulo="Famílias de defeito" valor={String(resumo.familias_de_defeito)} />
        <IndicadorCobertura valor={resumo.cobertura_documental} />
      </div>

      <Cartao
        titulo="Ocorrências por condição"
        complemento={`${resumo.dias_com_registro} dias com registro`}
        className="mb-4"
      >
        <div className="grid grid-cols-[3fr_2fr] gap-6">
          <GraficoCobertura defeitos={defeitos} />
          <LegendaCobertura defeitos={defeitos} />
        </div>
      </Cartao>

      {pendentes.length > 0 && (
        <Cartao
          titulo="Defeitos sem procedimento"
          complemento={`${numero(pendentes.reduce((s, c) => s + c.eventos, 0))} eventos afetados`}
          acao={
            <Botao icone="upload_file" onClick={() => aoNavegar("documentos")}>
              Cadastrar
            </Botao>
          }
          className="mb-4"
        >
          {pendentes
            .sort((a, b) => b.eventos - a.eventos)
            .map((condicao) => (
              <div
                key={condicao.condicao}
                className="flex items-center gap-3 py-2.5 border-b border-borda last:border-0"
              >
                <span className="w-[7px] h-[7px] rounded-full bg-alerta shrink-0" />
                <span className="font-semibold text-tinta text-[0.88rem]">{condicao.condicao}</span>
                <span className="text-[0.78rem] text-tinta-secundaria">
                  {numero(condicao.eventos)} eventos · {condicao.frequencia_diaria.toFixed(0)}/dia
                </span>
              </div>
            ))}
          <p className="text-[0.8rem] text-tinta-secundaria mt-3 leading-relaxed">
            O sistema não emite recomendação para esses defeitos. Cadastre o procedimento em{" "}
            <strong>Documentos</strong> para que passem a ser atendidos.
          </p>
        </Cartao>
      )}

      <div className="grid grid-cols-[3fr_2fr] gap-4 mb-4">
        <Cartao titulo="Eventos ao longo do tempo">
          <SerieTemporal dados={dados.eventos_por_dia} />
          <p className="text-[0.78rem] text-tinta-suave leading-relaxed mt-2">
            Cada campanha de ensaio concentra um modo de falha, em janelas quase disjuntas. É
            por isso que a data não entra como atributo do modelo: ela prediz o rótulo por
            construção.
          </p>
        </Cartao>

        <Cartao titulo="Rotação">
          <Rotacao dados={dados.eventos_por_rpm} />
          <p className="text-[0.78rem] text-tinta-suave leading-relaxed mt-2">
            Cinco rotações distintas em todo o histórico: são campanhas de bancada, não
            operação contínua.
          </p>
        </Cartao>
      </div>

      <Cartao
        titulo="Detalhamento por condição"
        complemento="grafias = formas distintas de anotação do operador"
      >
        <div className="mb-3">
          <label htmlFor="filtro-condicao" className="sr-only">
            Filtrar por condição
          </label>
          <Entrada
            id="filtro-condicao"
            valor={filtro}
            aoMudar={setFiltro}
            placeholder="Filtrar por condição…"
          />
        </div>
        <Tabela
          condicoes={condicoes.filter((c) =>
            c.condicao.toLowerCase().includes(filtro.toLowerCase()),
          )}
        />
        <p className="text-[0.78rem] text-tinta-suave mt-3">
          A normalização canônica reduz as 151 anotações do histórico às 17 condições reais.
        </p>
      </Cartao>
    </>
  );
}

function Indicador({ icone, rotulo, valor }: { icone: string; rotulo: string; valor: string }) {
  return (
    <Cartao>
      <div className="flex items-center gap-2 text-tinta-secundaria text-[0.78rem] font-medium">
        <Icone nome={icone} tamanho={17} />
        {rotulo}
      </div>
      <p className="text-[1.7rem] font-semibold text-tinta tracking-tight mt-1">{valor}</p>
    </Cartao>
  );
}

function IndicadorCobertura({ valor }: { valor: number }) {
  return (
    <Cartao>
      <div className="flex items-center gap-2 text-tinta-secundaria text-[0.78rem] font-medium">
        <Icone nome="verified" tamanho={17} />
        Cobertura documental
      </div>
      <p className="text-[1.7rem] font-semibold text-tinta tracking-tight mt-1">
        {percentual(valor)}
      </p>
      <div className="h-[5px] rounded-full bg-borda mt-2 overflow-hidden">
        <div className="h-full bg-sucesso" style={{ width: percentualCss(valor) }} />
      </div>
      <p className="text-[0.72rem] text-tinta-suave mt-1.5">dos eventos de defeito</p>
    </Cartao>
  );
}

function GraficoCobertura({ defeitos }: { defeitos: CondicaoNoHistorico[] }) {
  const dados = useMemo(
    () => [...defeitos].sort((a, b) => a.eventos - b.eventos),
    [defeitos],
  );

  return (
    <ResponsiveContainer width="100%" height={430}>
      <BarChart data={dados} layout="vertical" margin={{ left: 8, right: 48 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="condicao"
          width={140}
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 11, fill: "var(--color-tinta-secundaria)" }}
        />
        <Tooltip content={<Dica sufixo="eventos" />} cursor={{ fill: "var(--color-grade)" }} />
        <Bar dataKey="eventos" radius={[0, 4, 4, 0]} barSize={14}>
          {dados.map((condicao) => (
            <Cell
              key={condicao.condicao}
              fill={condicao.documentada ? COR_COBERTO : COR_SEM_DOCUMENTO}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/**
 * Legenda em lista, com o número ao lado do nome.
 *
 * Além de dar a leitura exata sem depender do cursor, serve de codificação secundária da
 * cor — exigência para o par verde/âmbar, que fica na faixa limítrofe sob protanopia.
 */
function LegendaCobertura({ defeitos }: { defeitos: CondicaoNoHistorico[] }) {
  return (
    <div className="overflow-y-auto max-h-[430px] pr-1">
      {[...defeitos]
        .sort((a, b) => b.eventos - a.eventos)
        .map((condicao) => (
          <div
            key={condicao.condicao}
            className="flex items-center gap-2.5 py-[7px] border-b border-borda last:border-0"
          >
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ background: condicao.documentada ? COR_COBERTO : COR_SEM_DOCUMENTO }}
            />
            <span className="text-[0.84rem] text-tinta">{condicao.condicao}</span>
            <span className="text-[0.72rem] text-tinta-suave">
              {condicao.documento ?? "sem procedimento"}
            </span>
            <span className="ml-auto text-[0.84rem] font-semibold text-tinta">
              {numero(condicao.eventos)}
            </span>
          </div>
        ))}
    </div>
  );
}

function SerieTemporal({ dados }: { dados: Record<string, number> }) {
  const serie = Object.entries(dados)
    .map(([dia, eventos]) => ({ dia, eventos }))
    .sort((a, b) => a.dia.localeCompare(b.dia));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={serie} margin={{ left: -18, right: 6, top: 6 }}>
        <defs>
          <linearGradient id="areaAcento" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-acento)" stopOpacity={0.22} />
            <stop offset="100%" stopColor="var(--color-acento)" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="dia"
          tickLine={false}
          axisLine={{ stroke: "var(--color-borda)" }}
          tick={{ fontSize: 10, fill: "var(--color-tinta-suave)" }}
          tickFormatter={(dia: string) => dia.slice(8, 10) + "/" + dia.slice(5, 7)}
          minTickGap={24}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 10, fill: "var(--color-tinta-suave)" }}
        />
        <Tooltip content={<Dica sufixo="eventos" />} />
        <Area
          type="monotone"
          dataKey="eventos"
          stroke="var(--color-acento)"
          strokeWidth={2}
          fill="url(#areaAcento)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Barras neutras, com a rotação dominante destacada no acento. */
function Rotacao({ dados }: { dados: Record<string, number> }) {
  const serie = Object.entries(dados).map(([rpm, eventos]) => ({ rpm, eventos }));
  const maximo = Math.max(...serie.map((item) => item.eventos));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={serie} margin={{ left: -18, right: 6, top: 6 }}>
        <XAxis
          dataKey="rpm"
          tickLine={false}
          axisLine={{ stroke: "var(--color-borda)" }}
          tick={{ fontSize: 11, fill: "var(--color-tinta-suave)" }}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 10, fill: "var(--color-tinta-suave)" }}
        />
        <Tooltip content={<Dica sufixo="eventos" />} cursor={{ fill: "var(--color-grade)" }} />
        <Bar dataKey="eventos" radius={[4, 4, 0, 0]}>
          {serie.map((item) => (
            <Cell
              key={item.rpm}
              fill={item.eventos === maximo ? "var(--color-acento)" : "var(--color-grade)"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function Tabela({ condicoes }: { condicoes: CondicaoNoHistorico[] }) {
  return (
    <div className="overflow-x-auto border border-borda rounded-lg">
      <table className="w-full text-[0.83rem]">
        <thead>
          <tr className="bg-fundo text-tinta-suave text-[0.72rem] uppercase tracking-wide">
            <th className="text-left font-semibold px-3 py-2.5">Condição</th>
            <th className="text-left font-semibold px-3 py-2.5">Tipo</th>
            <th className="text-right font-semibold px-3 py-2.5">Eventos</th>
            <th className="text-right font-semibold px-3 py-2.5">% do total</th>
            <th className="text-right font-semibold px-3 py-2.5">Grafias</th>
            <th className="text-right font-semibold px-3 py-2.5">Eventos/dia</th>
            <th className="text-left font-semibold px-3 py-2.5">Procedimento</th>
          </tr>
        </thead>
        <tbody>
          {condicoes.map((condicao) => (
            <tr key={condicao.condicao} className="border-t border-borda hover:bg-fundo transition">
              <td className="px-3 py-2 font-medium text-tinta">{condicao.condicao}</td>
              <td className="px-3 py-2 text-tinta-secundaria">{condicao.tipo_condicao}</td>
              <td className="px-3 py-2 text-right text-tinta-secundaria">
                {numero(condicao.eventos)}
              </td>
              <td className="px-3 py-2 text-right text-tinta-secundaria">
                {percentual(condicao.proporcao, 2)}
              </td>
              <td className="px-3 py-2 text-right text-tinta-secundaria">
                {condicao.rotulos_brutos}
              </td>
              <td className="px-3 py-2 text-right text-tinta-secundaria">
                {condicao.frequencia_diaria.toFixed(0)}
              </td>
              <td className="px-3 py-2">
                {condicao.documento ? (
                  <code className="text-[0.76rem] text-tinta-secundaria">
                    {condicao.documento}
                  </code>
                ) : (
                  <span className="text-tinta-suave">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
