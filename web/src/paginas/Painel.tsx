/** Painel do histórico monitorado. */

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  ReferenceArea,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  BlocoDeCampanha,
  CondicaoNoHistorico,
  EstadoSistema,
  PainelHistorico,
} from "../api/tipos";
import { Moldura } from "../componentes/graficos";
import {
  AvisoApi,
  Botao,
  Cartao,
  Carregando,
  Dica,
  Entrada,
  Etiqueta,
  Icone,
  RodapeCartao,
  Vazio,
} from "../componentes/base";
import { nomeCondicao, porNome } from "../condicoes";
import { numero, percentual, percentualCss } from "../formato";
import {
  AREA,
  COR,
  CURSOR,
  MARGEM,
  espacoMarcacao,
  espessuraBarra,
  espessuraLinha,
  larguraEixoCategoria,
  marcacao,
  medida,
  raioBarra,
} from "../estilo";
import { Topo } from "../componentes/navegacao";
import type { Pagina } from "../componentes/navegacao";

/** Verde é sempre *coberto por procedimento*; âmbar, sempre *sem respaldo*. */
const COR_COBERTO = COR.sucesso;
const COR_SEM_DOCUMENTO = COR.alerta;

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
            {sistema && <Etiqueta cor={COR.acento}>{sistema.modelo}</Etiqueta>}
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

      {/* A cobertura documental abre a fileira e ocupa duas colunas. É o guardrail
          expresso em número — a única métrica da tela que responde "quanto do problema
          o sistema se recusa a resolver" — e estava como quarto de quatro cartões
          iguais, com o mesmo peso de uma contagem de linhas. */}
      <div className="grid grid-cols-2 projetor:grid-cols-5 gap-4 mb-4">
        <IndicadorCobertura
          valor={resumo.cobertura_documental}
          pendentes={pendentes.length}
          eventosDescobertos={pendentes.reduce((soma, c) => soma + c.eventos, 0)}
          aoCadastrar={() => aoNavegar("documentos")}
        />
        <Indicador
          icone="database"
          rotulo="Eventos monitorados"
          valor={numero(resumo.total_eventos)}
          nota={`${resumo.dias_com_registro} dias com registro`}
        />
        <Indicador
          icone="warning"
          rotulo="Defeitos"
          valor={numero(resumo.total_defeitos)}
          nota={`${numero(resumo.total_estados)} em estado operacional`}
        />
        <Indicador
          icone="category"
          rotulo="Famílias de defeito"
          valor={String(resumo.familias_de_defeito)}
          nota="das 151 anotações do operador"
        />
      </div>

      <Cartao
        titulo="Ocorrências por condição"
        complemento={`${defeitos.length} famílias de defeito, ordenadas por volume`}
        className="mb-4"
      >
        <div className="grid grid-cols-1 xl:grid-cols-[3fr_2fr] gap-6">
          <GraficoCobertura defeitos={defeitos} />
          <LegendaCobertura defeitos={defeitos} />
        </div>
      </Cartao>

      {pendentes.length > 0 && (
        <Cartao
          titulo="Defeitos sem procedimento"
          complemento={`${numero(pendentes.reduce((s, c) => s + c.eventos, 0))} eventos afetados`}
          className="mb-4"
        >
          {pendentes
            .sort((a, b) => b.eventos - a.eventos)
            .map((condicao) => (
              <div
                key={condicao.condicao}
                className="flex flex-wrap items-center gap-x-3 py-2.5 border-b border-borda last:border-0"
              >
                <span className="w-2 h-2 rounded-full bg-alerta shrink-0" />
                <span className="font-semibold text-tinta text-corpo">
                  {nomeCondicao(condicao.condicao)}
                </span>
                <code className="text-nota text-tinta-suave">{condicao.condicao}</code>
                <span className="text-nota text-tinta-secundaria">
                  {numero(condicao.eventos)} eventos · {condicao.frequencia_diaria.toFixed(0)}/dia
                </span>
              </div>
            ))}
          <p className="text-nota text-tinta-secundaria mt-3">
            O sistema não emite recomendação para esses defeitos. Cadastre o procedimento em{" "}
            <strong>Documentos</strong> para que passem a ser atendidos.
          </p>
        </Cartao>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[3fr_2fr] gap-4 mb-4">
        <Cartao titulo="Eventos ao longo do tempo" complemento="faixas = campanhas de ensaio">
          <SerieTemporal dados={dados.eventos_por_dia} campanhas={dados.campanhas} />
          {/* A legenda anterior dizia "janelas quase disjuntas", e isso não se sustentava
              nos dados: medidas por primeiro e último evento, as janelas de cada condição
              se sobrepõem quase inteiramente — `desbalanceado` é ensaiado em abril e volta
              em junho. Medido pela condição que domina cada dia, o histórico mostra dois
              regimes, e o argumento do ADR-003 sobrevive aos dois. */}
          <p className="text-nota text-tinta-suave mt-2">
            Os ensaios se sucedem em blocos: até 28/05 cada trecho concentra um modo de
            falha, com 61% a 100% dos eventos do dia numa só condição; de 01/06 em diante
            as campanhas se sobrepõem e a dominância cai para 22% a 63%. Nos dois regimes a
            data carrega informação sobre o rótulo — é por isso que ela não entra como
            atributo do modelo, e por isso que validar por amostragem aleatória infla a
            acurácia.
          </p>
        </Cartao>

        <Cartao titulo="Rotação">
          <Rotacao dados={dados.eventos_por_rpm} />
          <p className="text-nota text-tinta-suave mt-2">
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
        {(() => {
          // O filtro casa contra o nome em português **e** contra o identificador:
          // quem digita "rolamento" e quem digita "bearing_inner" procuram a mesma
          // linha, e só um dos dois estava contemplado.
          const busca = filtro.trim().toLowerCase();
          const visiveis = condicoes.filter(
            (c) =>
              c.condicao.toLowerCase().includes(busca) ||
              nomeCondicao(c.condicao).toLowerCase().includes(busca),
          );
          return visiveis.length ? (
            <Tabela condicoes={visiveis} />
          ) : (
            <Vazio
              icone="search_off"
              titulo="Nenhuma condição corresponde ao filtro"
              descricao={`Nada encontrado para "${filtro}". As 17 condições canônicas cobrem 12 defeitos e 5 estados operacionais.`}
            />
          );
        })()}
        <p className="text-nota text-tinta-suave mt-3">
          A normalização canônica reduz as 151 anotações do histórico às 17 condições reais.
        </p>
      </Cartao>
    </>
  );
}

/**
 * Cartão de indicador.
 *
 * A ordem é rótulo → número → nota, e não o contrário: o número é o único elemento
 * da tela lido a três metros, então nada pode ficar acima dele disputando atenção.
 */
function Indicador({
  icone,
  rotulo,
  valor,
  nota,
  acao,
}: {
  icone: string;
  rotulo: string;
  valor: string;
  nota: string;
  acao?: { rotulo: string; ir: () => void };
}) {
  return (
    <Cartao rodape={acao && <RodapeCartao rotulo={acao.rotulo} onClick={acao.ir} />}>
      <div className="flex items-center gap-2 text-tinta-secundaria text-nota font-medium">
        <Icone nome={icone} tamanho="pequeno" />
        <span className="truncate">{rotulo}</span>
      </div>
      <p className="tabular text-destaque text-tinta mt-1">{valor}</p>
      <p className="text-nota text-tinta-suave">{nota}</p>
    </Cartao>
  );
}

/**
 * Cobertura documental — o cartão que carrega a tese.
 *
 * A barra mostra as duas frações, e não só a coberta sobre um trilho vazio: o que
 * falta é decisão registrada (ADR-011), não lacuna a ser tapada, e desenhá-la em
 * âmbar diz isso sem uma linha de texto. Vazio, o trilho convidava à leitura
 * "faltou fazer".
 */
function IndicadorCobertura({
  valor,
  pendentes,
  eventosDescobertos,
  aoCadastrar,
}: {
  valor: number;
  pendentes: number;
  eventosDescobertos: number;
  aoCadastrar: () => void;
}) {
  return (
    <Cartao
      className="col-span-2"
      rodape={
        pendentes > 0 && (
          <RodapeCartao
            rotulo={`Cadastrar ${pendentes} procedimentos pendentes`}
            onClick={aoCadastrar}
          />
        )
      }
    >
      <div className="flex items-center gap-2 text-tinta-secundaria text-nota font-medium">
        <Icone nome="verified" tamanho="pequeno" />
        <span className="truncate">Cobertura documental</span>
      </div>
      <p className="tabular text-destaque text-tinta mt-1">{percentual(valor)}</p>

      <div className="flex h-2 rounded-full overflow-hidden mt-2 gap-px">
        <div className="bg-sucesso" style={{ width: percentualCss(valor) }} />
        <div className="bg-alerta flex-1" />
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-nota">
        <span className="flex items-center gap-1.5 text-tinta-secundaria">
          <span className="w-2 h-2 rounded-full bg-sucesso shrink-0" />
          eventos com procedimento
        </span>
        <span className="flex items-center gap-1.5 text-tinta-secundaria">
          <span className="w-2 h-2 rounded-full bg-alerta shrink-0" />
          <span className="tabular">{numero(eventosDescobertos)}</span> sem — o sistema
          recusa
        </span>
      </div>
    </Cartao>
  );
}

function GraficoCobertura({ defeitos }: { defeitos: CondicaoNoHistorico[] }) {
  const dados = useMemo(() => [...defeitos].sort((a, b) => a.eventos - b.eventos), [defeitos]);
  const raio = raioBarra();

  return (
    <Moldura altura="alto">
      <BarChart data={dados} layout="vertical" margin={MARGEM.categorias}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="condicao"
          width={larguraEixoCategoria()}
          tickLine={false}
          axisLine={false}
          tick={marcacao(false)}
        />
        <Tooltip content={<Dica sufixo="eventos" />} cursor={CURSOR} />
        <Bar dataKey="eventos" radius={[0, raio, raio, 0]} barSize={espessuraBarra()}>
          {dados.map((condicao) => (
            <Cell
              key={condicao.condicao}
              fill={condicao.documentada ? COR_COBERTO : COR_SEM_DOCUMENTO}
            />
          ))}
        </Bar>
      </BarChart>
    </Moldura>
  );
}

/**
 * Legenda em lista, com o número ao lado do nome.
 *
 * Além de dar a leitura exata sem depender do cursor, serve de codificação
 * secundária da cor — exigência para o par verde/âmbar, que fica na faixa limítrofe
 * sob protanopia.
 */
function LegendaCobertura({ defeitos }: { defeitos: CondicaoNoHistorico[] }) {
  return (
    <div className="overflow-y-auto max-h-[var(--altura-grafico-alto)] pr-1">
      {[...defeitos]
        .sort((a, b) => b.eventos - a.eventos)
        .map((condicao) => (
          <div
            key={condicao.condicao}
            className="flex items-center gap-2.5 py-1.5 border-b border-borda last:border-0"
          >
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ background: condicao.documentada ? COR_COBERTO : COR_SEM_DOCUMENTO }}
            />
            <span className="text-corpo text-tinta truncate">
              {nomeCondicao(condicao.condicao)}
            </span>
            <span className="text-nota text-tinta-suave truncate hidden sm:block">
              {condicao.documento ?? "sem procedimento"}
            </span>
            <span className="tabular ml-auto text-corpo font-semibold text-tinta shrink-0">
              {numero(condicao.eventos)}
            </span>
          </div>
        ))}
    </div>
  );
}

/**
 * Série temporal com as campanhas de ensaio marcadas ao fundo.
 *
 * As faixas são **neutras e alternadas**, não coloridas por condição. São dezoito, e a
 * paleta tem um acento e três status reservados: colorir cada uma exigiria inventar
 * quatorze cores e destruiria o significado das que existem. A identidade da campanha é
 * carregada por posição e rótulo, que é a política registrada em `index.css` para
 * categorias numerosas — a informação aqui é *quando cada ensaio ocorreu*, não qual cor
 * corresponde a qual defeito.
 *
 * Só recebem rótulo os blocos de dois dias ou mais; nos de um dia o nome não caberia e
 * colidiria com o vizinho.
 */
function SerieTemporal({
  dados,
  campanhas,
}: {
  dados: Record<string, number>;
  campanhas: BlocoDeCampanha[];
}) {
  const serie = Object.entries(dados)
    .map(([dia, eventos]) => ({ dia, eventos }))
    .sort((a, b) => a.dia.localeCompare(b.dia));

  return (
    <Moldura>
      <AreaChart data={serie} margin={MARGEM.serie}>
        {campanhas.map((bloco, indice) => (
          <ReferenceArea
            key={`${bloco.condicao}-${bloco.primeiro_dia}`}
            x1={bloco.primeiro_dia}
            x2={bloco.ultimo_dia}
            fill={indice % 2 === 0 ? COR.grade : "transparent"}
            fillOpacity={1}
            label={
              bloco.dias >= 2
                ? {
                    value: nomeCondicao(bloco.condicao),
                    position: "insideTop",
                    fill: COR.tintaSuave,
                    fontSize: medida("--text-nota"),
                  }
                : undefined
            }
          />
        ))}
        <defs>
          <linearGradient id="areaAcento" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={COR.acento} stopOpacity={AREA.topo} />
            <stop offset="100%" stopColor={COR.acento} stopOpacity={AREA.base} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="dia"
          tickLine={false}
          axisLine={{ stroke: COR.borda }}
          tick={marcacao()}
          tickFormatter={(dia: string) => dia.slice(8, 10) + "/" + dia.slice(5, 7)}
          minTickGap={espacoMarcacao()}
        />
        <YAxis tickLine={false} axisLine={false} tick={marcacao()} />
        <Tooltip content={<Dica sufixo="eventos" />} />
        <Area
          type="monotone"
          dataKey="eventos"
          stroke={COR.acento}
          strokeWidth={espessuraLinha()}
          fill="url(#areaAcento)"
        />
      </AreaChart>
    </Moldura>
  );
}

/** Barras neutras, com a rotação dominante destacada no acento. */
function Rotacao({ dados }: { dados: Record<string, number> }) {
  const serie = Object.entries(dados).map(([rpm, eventos]) => ({ rpm, eventos }));
  const maximo = Math.max(...serie.map((item) => item.eventos));
  const raio = raioBarra();

  return (
    <Moldura>
      <BarChart data={serie} margin={MARGEM.serie}>
        <XAxis dataKey="rpm" tickLine={false} axisLine={{ stroke: COR.borda }} tick={marcacao()} />
        <YAxis tickLine={false} axisLine={false} tick={marcacao()} />
        <Tooltip content={<Dica sufixo="eventos" />} cursor={CURSOR} />
        <Bar dataKey="eventos" radius={[raio, raio, 0, 0]}>
          {serie.map((item) => (
            <Cell key={item.rpm} fill={item.eventos === maximo ? COR.acento : COR.grade} />
          ))}
        </Bar>
      </BarChart>
    </Moldura>
  );
}

/**
 * Detalhamento por condição, ordenável.
 *
 * Dezessete linhas com filtro e sem ordenação obrigavam a ler a coluna inteira para
 * responder a pergunta mais óbvia que a tabela suscita — *qual defeito mais ocorre?*.
 *
 * A ordem inicial é por volume decrescente, e não alfabética: quem abre esta tabela
 * quer saber o que domina o histórico, não o que começa com "a".
 */
type Coluna = keyof Pick<
  CondicaoNoHistorico,
  "condicao" | "tipo_condicao" | "eventos" | "proporcao" | "rotulos_brutos" | "frequencia_diaria"
>;

const COLUNAS: { chave: Coluna; rotulo: string; numerica: boolean }[] = [
  { chave: "condicao", rotulo: "Condição", numerica: false },
  { chave: "tipo_condicao", rotulo: "Tipo", numerica: false },
  { chave: "eventos", rotulo: "Eventos", numerica: true },
  { chave: "proporcao", rotulo: "% do total", numerica: true },
  { chave: "rotulos_brutos", rotulo: "Grafias", numerica: true },
  { chave: "frequencia_diaria", rotulo: "Eventos/dia", numerica: true },
];

function Tabela({ condicoes }: { condicoes: CondicaoNoHistorico[] }) {
  const [ordem, setOrdem] = useState<{ coluna: Coluna; crescente: boolean }>({
    coluna: "eventos",
    crescente: false,
  });

  function ordenarPor(coluna: Coluna) {
    setOrdem((atual) =>
      atual.coluna === coluna
        ? { coluna, crescente: !atual.crescente }
        : // Ao trocar de coluna, texto começa em A→Z e número em maior→menor: é a
          // primeira leitura que cada tipo de dado pede.
          { coluna, crescente: !COLUNAS.find((c) => c.chave === coluna)?.numerica },
    );
  }

  const ordenadas = useMemo(() => {
    const sinal = ordem.crescente ? 1 : -1;
    return [...condicoes].sort((a, b) => {
      const x = a[ordem.coluna];
      const y = b[ordem.coluna];
      if (typeof x === "number" && typeof y === "number") return (x - y) * sinal;
      // A condição ordena pelo nome em português, que é o que está sendo lido.
      if (ordem.coluna === "condicao") return porNome(String(x), String(y)) * sinal;
      return String(x).localeCompare(String(y), "pt-BR") * sinal;
    });
  }, [condicoes, ordem]);

  return (
    <div className="overflow-x-auto border border-borda rounded-controle">
      <table className="tabular w-full text-corpo">
        <thead>
          <tr className="bg-fundo text-tinta-suave rotulo">
            {COLUNAS.map((coluna) => {
              const atual = ordem.coluna === coluna.chave;
              return (
                <th
                  key={coluna.chave}
                  scope="col"
                  aria-sort={atual ? (ordem.crescente ? "ascending" : "descending") : "none"}
                  className={coluna.numerica ? "text-right" : "text-left"}
                >
                  <button
                    onClick={() => ordenarPor(coluna.chave)}
                    className={`foco w-full flex items-center gap-1 px-3 py-2.5 hover:text-tinta transition ${
                      coluna.numerica ? "justify-end" : ""
                    } ${atual ? "text-acento" : ""}`}
                  >
                    {coluna.rotulo}
                    <Icone
                      nome={
                        atual ? (ordem.crescente ? "arrow_upward" : "arrow_downward") : "unfold_more"
                      }
                      tamanho="pequeno"
                      className={atual ? "" : "opacity-45"}
                    />
                  </button>
                </th>
              );
            })}
            <th scope="col" className="text-left font-semibold px-3 py-2.5">
              Procedimento
            </th>
          </tr>
        </thead>
        <tbody>
          {ordenadas.map((condicao) => (
            <tr
              key={condicao.condicao}
              className="border-t border-borda hover:bg-fundo transition"
            >
              <td className="px-3 py-2">
                <span className="block font-medium text-tinta whitespace-nowrap">
                  {nomeCondicao(condicao.condicao)}
                </span>
                <code className="block text-nota text-tinta-suave">{condicao.condicao}</code>
              </td>
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
                  <code className="text-nota text-tinta-secundaria">{condicao.documento}</code>
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
