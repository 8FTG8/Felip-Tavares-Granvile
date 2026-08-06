/**
 * Barra lateral e cabeçalho de página.
 *
 * A navegação é escura dentro de um produto claro, para separar numa leitura a moldura
 * permanente do conteúdo da tarefa. Os itens são agrupados por natureza: o que se faz
 * no dia a dia e o que se configura.
 *
 * Os defeitos sem procedimento aparecem só como contagem ao lado de *Documentos*. Os
 * nomes por extenso ficam no cartão dedicado do Painel, com eventos por dia.
 *
 * Acima de 1024px a lateral é fixa e acompanha a rolagem; abaixo disso vira gaveta,
 * porque 244px sobre tela de projetor comprimiriam o conteúdo até as tabelas quebrarem.
 */

import { useEffect } from "react";
import type { ReactNode } from "react";
import type { CoberturaDocumental, EstadoSistema } from "../api/tipos";
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
  aberta,
  aoFechar,
}: {
  atual: Pagina;
  aoNavegar: (pagina: Pagina) => void;
  sistema: EstadoSistema | null;
  cobertura: CoberturaDocumental[];
  aberta: boolean;
  aoFechar: () => void;
}) {
  const pendentes = cobertura.filter((c) => !c.documentada);

  // Escape fecha a gaveta. Sem isso, quem navega por teclado em tela estreita fica
  // preso entre a sobreposição e o conteúdo.
  useEffect(() => {
    if (!aberta) return;
    const aoTeclar = (evento: KeyboardEvent) => evento.key === "Escape" && aoFechar();
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [aberta, aoFechar]);

  return (
    <>
      {/* Sobreposição da gaveta. Só existe abaixo de 1024px e só quando aberta. */}
      {aberta && (
        <div
          onClick={aoFechar}
          aria-hidden="true"
          className="lg:hidden fixed inset-0 z-[var(--camada-veu)] bg-tinta/45"
        />
      )}

      <aside
        className={`fixed lg:sticky top-0 z-[var(--camada-gaveta)] h-screen shrink-0 flex flex-col bg-lateral transition-transform w-[var(--largura-lateral)] lg:w-[var(--largura-lateral-media)] xl:w-[var(--largura-lateral)] ${
          // `invisible` importa mais que a translação: só deslocada para fora da tela,
          // a gaveta continuaria na ordem de tabulação, com seis paradas em elementos
          // que ninguém vê. `lg:visible` a devolve quando deixa de ser gaveta.
          aberta
            ? "translate-x-0"
            : "-translate-x-full invisible lg:visible lg:translate-x-0"
        }`}
      >
        <div className="px-4 pt-5 pb-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-controle bg-lateral-acento flex items-center justify-center shrink-0">
            <Icone nome="settings_suggest" tamanho="medio" className="text-tinta-invertida" />
          </div>
          <div className="text-corpo-forte font-bold text-lateral-tinta leading-tight">
            <p>Manutenção</p>
            <p>Prescritiva</p>
          </div>

          <button
            onClick={aoFechar}
            aria-label="Fechar navegação"
            className="foco-lateral lg:hidden ml-auto p-1 rounded-controle text-lateral-tinta-suave hover:bg-lateral-elevada"
          >
            <Icone nome="close" tamanho="medio" />
          </button>
        </div>

        <div className="h-px bg-lateral-borda mx-4" />

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {SECOES.map((secao) => (
            <div key={secao.titulo} className="mb-5 last:mb-0">
              <p className="rotulo text-lateral-tinta-suave px-3 mb-2">
                {secao.titulo}
              </p>

              {secao.destinos.map((destino) => {
                const ativo = atual === destino.chave;
                const contar = destino.chave === "documentos" && pendentes.length > 0;
                return (
                  /* O item corrente é preenchido no acento: na lateral escura um
                     realce sutil desaparece a dois metros de distância. */
                  <button
                    key={destino.chave}
                    onClick={() => aoNavegar(destino.chave)}
                    aria-current={ativo ? "page" : undefined}
                    // O algarismo é o único portador da informação, e "3" sozinho não
                    // diz três do quê.
                    aria-label={
                      contar
                        ? `${destino.rotulo}, ${pendentes.length} sem procedimento`
                        : undefined
                    }
                    className={`foco-lateral w-full flex items-center gap-3 px-3 py-2 rounded-controle text-corpo transition ${
                      ativo
                        ? "bg-lateral-acento text-tinta-invertida font-semibold"
                        : "text-lateral-tinta-suave hover:bg-lateral-elevada hover:text-lateral-tinta font-medium"
                    }`}
                  >
                    <Icone nome={destino.icone} tamanho="medio" />
                    <span className="truncate">{destino.rotulo}</span>
                    {/* Pílula neutra, só o algarismo em âmbar: âmbar chapado sobre
                        preto vira mancha marrom, e uma contagem não é um estado. */}
                    {contar && (
                      <span
                        aria-hidden="true"
                        className={`ml-auto text-nota font-semibold rounded-full px-2 ${
                          ativo
                            ? "bg-tinta-invertida/25 text-tinta-invertida"
                            : "bg-lateral-elevada text-lateral-alerta"
                        }`}
                      >
                        {pendentes.length}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="px-3 pb-4">
          <CartaoSistema sistema={sistema} />
          <p className="text-nota text-lateral-tinta-suave mt-3 px-1">
            As recomendações vêm exclusivamente dos procedimentos técnicos da empresa.
            Defeitos sem procedimento cadastrado não recebem recomendação.
          </p>
        </div>
      </aside>
    </>
  );
}

/** Estado do serviço, fixo no pé da lateral. */
function CartaoSistema({ sistema }: { sistema: EstadoSistema | null }) {
  const conectada = sistema !== null;
  const cor = conectada
    ? "var(--color-lateral-sucesso)"
    : "var(--color-lateral-critico)";

  return (
    <div className="rounded-cartao bg-lateral-elevada p-3">
      <div className="flex items-center gap-2">
        {/* Halo por color-mix: os tokens são variáveis CSS, e concatenar opacidade em
            hexadecimal produziria `var(--color-sucesso)22`, que o navegador descarta. */}
        <span
          className="w-2 h-2 rounded-full shrink-0"
          style={{
            background: cor,
            boxShadow: `0 0 0 3px color-mix(in srgb, ${cor} 22%, transparent)`,
          }}
        />
        <span className="text-corpo font-medium text-lateral-tinta">
          {conectada ? "API conectada" : "API indisponível"}
        </span>
      </div>

      {sistema && (
        <div className="mt-2 pt-2 border-t border-lateral-borda">
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
    <div className="flex justify-between items-center gap-2 py-0.5">
      <span className="text-nota text-lateral-tinta-suave shrink-0">{rotulo}</span>
      <span className="text-nota text-lateral-tinta font-medium truncate">{valor}</span>
    </div>
  );
}

/** Cabeçalho que aparece apenas quando a lateral está recolhida em gaveta. */
export function BarraMovel({ aoAbrir }: { aoAbrir: () => void }) {
  return (
    <div className="lg:hidden sticky top-0 z-[var(--camada-barra)] flex items-center gap-3 bg-superficie border-b border-borda px-4 py-3">
      <button
        onClick={aoAbrir}
        aria-label="Abrir navegação"
        className="foco p-1 rounded-controle text-tinta-secundaria hover:bg-ativo"
      >
        <Icone nome="menu" tamanho="grande" />
      </button>
      <div className="w-7 h-7 rounded-sutil bg-acento flex items-center justify-center shrink-0">
        <Icone nome="settings_suggest" tamanho="pequeno" className="text-tinta-invertida" />
      </div>
      <p className="text-corpo font-bold text-tinta">Manutenção Prescritiva</p>
    </div>
  );
}

/** Cabeçalho de página: título, descrição, etiquetas de contexto e ação primária. */
export function Topo({
  titulo,
  descricao,
  info,
  etiquetas,
  acao,
}: {
  titulo: string;
  descricao: string;
  /**
   * Ícone de informação, imediatamente à direita do título — tipicamente um
   * `<SobreATela>`. Opcional: uma tela sem explicação declarada não ganha um botão que
   * não abre nada.
   */
  info?: ReactNode;
  etiquetas?: ReactNode;
  acao?: ReactNode;
}) {
  return (
    <header className="flex flex-col md:flex-row md:items-start gap-4 md:gap-6 pb-5 mb-5 border-b border-borda">
      <div className="min-w-0">
        {/* `items-center` alinha o ícone pela altura do texto, e não pela caixa da
            linha: encostado na linha de base, ele fica visivelmente baixo ao lado de um
            título de 22px. */}
        <div className="flex items-center gap-1.5">
          <h1 className="text-titulo-pagina">{titulo}</h1>
          {info}
        </div>
        <p className="text-corpo text-tinta-secundaria mt-1 max-w-2xl">{descricao}</p>
      </div>
      <div className="md:ml-auto flex flex-row-reverse md:flex-col items-center md:items-end justify-end gap-2 shrink-0">
        {etiquetas && (
          <div className="flex gap-1.5 flex-wrap justify-start md:justify-end">{etiquetas}</div>
        )}
        {acao}
      </div>
    </header>
  );
}
