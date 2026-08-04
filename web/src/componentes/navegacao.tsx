/**
 * Barra lateral e cabeçalho de página.
 *
 * A navegação é agrupada por natureza da tarefa — o que se faz no dia a dia e o que se
 * configura. Quatro itens soltos não formam uma lista legível; agrupados, formam.
 *
 * Os defeitos sem procedimento aparecem como sub-itens de *Documentos*, ligados por uma
 * guia vertical. Não é enfeite: responde, sem que ninguém precise abrir a tela, à única
 * pergunta que o operador faz o tempo todo — *o que ainda está sem procedimento?*
 */

import type { ReactNode } from "react";
import type { CoberturaDocumental, EstadoSistema } from "../api/tipos";
import type { Tema } from "../tema";
import { Icone } from "./base";

export type Pagina = "painel" | "analise" | "assistente" | "documentos";

interface Destino {
  chave: Pagina;
  rotulo: string;
  icone: string;
}

const SECOES: { titulo: string; destinos: Destino[] }[] = [
  {
    titulo: "Operação",
    destinos: [
      { chave: "painel", rotulo: "Painel", icone: "monitoring" },
      { chave: "analise", rotulo: "Análise de evento", icone: "vital_signs" },
      { chave: "assistente", rotulo: "Assistente técnico", icone: "forum" },
    ],
  },
  {
    titulo: "Configuração",
    destinos: [{ chave: "documentos", rotulo: "Documentos", icone: "description" }],
  },
];

export function BarraLateral({
  atual,
  aoNavegar,
  sistema,
  cobertura,
  tema,
  aoAlternarTema,
}: {
  atual: Pagina;
  aoNavegar: (pagina: Pagina) => void;
  sistema: EstadoSistema | null;
  cobertura: CoberturaDocumental[];
  tema: Tema;
  aoAlternarTema: () => void;
}) {
  const pendentes = cobertura.filter((c) => !c.documentada);

  return (
    <aside className="w-[268px] shrink-0 h-screen sticky top-0 bg-superficie border-r border-borda flex flex-col">
      <div className="px-4 pt-5 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-tinta flex items-center justify-center shrink-0">
            <Icone nome="settings_suggest" tamanho={20} className="text-white" />
          </div>
          <div className="leading-[1.15]">
            <p className="text-[0.95rem] font-bold text-tinta">Manutenção</p>
            <p className="text-[0.95rem] font-bold text-tinta">Prescritiva</p>
          </div>
        </div>
      </div>

      <div className="h-px bg-borda mx-4" />

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {SECOES.map((secao) => (
          <div key={secao.titulo} className="mb-5 last:mb-0">
            <p className="text-[0.72rem] text-tinta-suave px-3 mb-1.5">{secao.titulo}</p>

            {secao.destinos.map((destino) => {
              const ativo = atual === destino.chave;
              return (
                <div key={destino.chave}>
                  <button
                    onClick={() => aoNavegar(destino.chave)}
                    aria-current={ativo ? "page" : undefined}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-[10px] text-[0.88rem] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-acento/40 ${
                      ativo
                        ? "bg-ativo text-tinta font-semibold ring-1 ring-borda"
                        : "text-tinta-secundaria hover:bg-fundo hover:text-tinta font-medium"
                    }`}
                  >
                    <Icone nome={destino.icone} tamanho={19} />
                    {destino.rotulo}
                    {destino.chave === "documentos" && pendentes.length > 0 && (
                      <span className="ml-auto text-[0.7rem] font-semibold text-tinta-secundaria bg-fundo border border-borda rounded-full px-2 py-0.5">
                        {pendentes.length}
                      </span>
                    )}
                  </button>

                  {destino.chave === "documentos" && pendentes.length > 0 && (
                    <div className="relative ml-6 mt-1 mb-1 pl-4">
                      <span className="absolute left-0 top-0 bottom-3 w-px bg-borda" />
                      {pendentes.map((pendente) => (
                        <div
                          key={pendente.condicao}
                          className="relative py-1 text-[0.79rem] text-tinta-secundaria"
                        >
                          <span className="absolute left-[-16px] top-1/2 w-[9px] h-px bg-borda" />
                          <span className="inline-block w-1.5 h-1.5 rounded-full bg-alerta mr-2 align-middle" />
                          {pendente.condicao}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="px-3 pb-4">
        <p className="text-[0.72rem] text-tinta-suave px-3 mb-1.5">Sistema</p>
        <CartaoSistema sistema={sistema} />
        <button
          onClick={aoAlternarTema}
          aria-pressed={tema === "escuro"}
          className="w-full flex items-center gap-2.5 mt-3 px-3 py-2 rounded-[10px] text-[0.82rem] text-tinta-secundaria hover:bg-fundo hover:text-tinta transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-acento/40"
          title={tema === "claro" ? "Mudar para o tema escuro" : "Mudar para o tema claro"}
        >
          <Icone nome={tema === "claro" ? "dark_mode" : "light_mode"} tamanho={18} />
          Tema {tema === "claro" ? "escuro" : "claro"}
        </button>

        <p className="text-[0.71rem] text-tinta-suave leading-relaxed mt-2 px-1 pt-3 border-t border-borda">
          As recomendações vêm exclusivamente dos procedimentos técnicos da empresa.
          Defeitos sem procedimento cadastrado não recebem recomendação.
        </p>
      </div>
    </aside>
  );
}

function CartaoSistema({ sistema }: { sistema: EstadoSistema | null }) {
  const conectada = sistema !== null;
  const cor = conectada ? "var(--color-sucesso)" : "var(--color-critico)";

  return (
    <div className="border border-borda rounded-lg bg-fundo p-3">
      <div className="flex items-center gap-2">
        {/* O halo usa color-mix porque os tokens são variáveis CSS: concatenar opacidade
            em hexadecimal produziria `var(--color-sucesso)22`, que o navegador descarta. */}
        <span
          className="w-[7px] h-[7px] rounded-full shrink-0"
          style={{
            background: cor,
            boxShadow: `0 0 0 3px color-mix(in srgb, ${cor} 18%, transparent)`,
          }}
        />
        <span className="text-[0.8rem] font-medium text-tinta">
          {conectada ? "API conectada" : "API indisponível"}
        </span>
      </div>

      {sistema && (
        <div className="mt-2 pt-2 border-t border-borda">
          <LinhaEstado rotulo="Modelo" valor={sistema.modelo.split(":")[0]} />
          <LinhaEstado rotulo="Variante" valor={sistema.modelo.split(":").slice(-1)[0]} />
          <LinhaEstado rotulo="Limiar" valor={sistema.limiar_relevancia.toFixed(3)} />
          <LinhaEstado
            rotulo="Cobertura"
            valor={`${sistema.familias_documentadas}/${sistema.familias_totais} famílias`}
          />
        </div>
      )}
    </div>
  );
}

function LinhaEstado({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="flex justify-between items-center py-[3px]">
      <span className="text-[0.74rem] text-tinta-suave">{rotulo}</span>
      <span className="text-[0.74rem] text-tinta-secundaria font-medium">{valor}</span>
    </div>
  );
}

/** Cabeçalho de página: título, descrição, etiquetas de contexto e ação primária. */
export function Topo({
  titulo,
  descricao,
  etiquetas,
  acao,
}: {
  titulo: string;
  descricao: string;
  etiquetas?: ReactNode;
  acao?: ReactNode;
}) {
  return (
    <header className="flex items-start gap-6 pb-5 mb-6 border-b border-borda">
      <div className="min-w-0">
        <h1 className="text-[1.6rem]">{titulo}</h1>
        <p className="text-[0.88rem] text-tinta-secundaria mt-1 max-w-2xl leading-relaxed">
          {descricao}
        </p>
      </div>
      <div className="ml-auto flex flex-col items-end gap-2 shrink-0">
        {etiquetas && <div className="flex gap-1.5 flex-wrap justify-end">{etiquetas}</div>}
        {acao}
      </div>
    </header>
  );
}
