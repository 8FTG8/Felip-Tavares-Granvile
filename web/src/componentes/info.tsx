/**
 * Ícone de informação ao lado do título da tela, com o diálogo que o explica.
 *
 * Uma tela deste produto mistura números medidos, decisões de projeto e recusas
 * deliberadas — "9 de 12 famílias" e "o sistema não recomenda" só se leem certo com o
 * contexto ao lado. Este componente é onde esse contexto mora, à distância de um clique
 * do título, em vez de espalhado em legendas que competem com o dado.
 *
 * **Todo o conteúdo vem por parâmetro.** O componente não conhece tela alguma: recebe
 * título, descrição e seções, e serve a qualquer uma. Acrescentar a próxima é escrever
 * um objeto de conteúdo e passá-lo ao `Topo`.
 *
 * A estrutura — parágrafo de abertura, seções rotuladas e itens com ícone, título e
 * descrição — segue o padrão dos diálogos de informação do `caree_app`
 * (`lib/features/professional/widgets/infos`), adaptado aos tokens deste projeto.
 */

import { useRef } from "react";
import { Botao, Icone } from "./base";

/** Item explicado dentro de uma seção: um indicador, um cartão, um gráfico. */
export interface ItemDeInfo {
  titulo: string;
  descricao: string;
  /** Nome do ícone no Material Symbols. O padrão acompanha os itens neutros. */
  icone?: string;
  /**
   * Cor do ícone. `alerta` para o que exige atenção da equipe, `critico` para o que é
   * destrutivo ou irreversível — os mesmos significados que os status têm no resto da
   * interface, e por isso nunca escolhidos por estética.
   */
  tom?: "acento" | "alerta" | "critico";
  /** Aviso curto abaixo da descrição, quando há uma ressalva que muda a leitura. */
  nota?: string;
}

/** Bloco de itens sob um rótulo — costuma espelhar uma faixa visível da tela. */
export interface SecaoDeInfo {
  rotulo: string;
  itens: ItemDeInfo[];
}

/** Conteúdo completo de um diálogo, para ser declarado ao lado da tela que descreve. */
export interface ConteudoDaTela {
  titulo: string;
  descricao: string;
  secoes: SecaoDeInfo[];
}

const TONS = {
  acento: "bg-acento-suave text-acento",
  alerta: "bg-alerta-suave text-alerta-texto",
  critico: "bg-critico-suave text-critico",
} as const;

export function SobreATela({ titulo, descricao, secoes }: ConteudoDaTela) {
  const dialogo = useRef<HTMLDialogElement>(null);

  return (
    <>
      <button
        type="button"
        onClick={() => dialogo.current?.showModal()}
        aria-label={`Sobre a tela ${titulo}`}
        className="foco inline-flex items-center justify-center rounded-full p-1 text-tinta-suave hover:text-acento hover:bg-acento-suave transition"
      >
        <Icone nome="info" tamanho="medio" />
      </button>

      <dialog
        ref={dialogo}
        aria-labelledby="titulo-sobre-a-tela"
        className="dialogo"
        // O clique no véu tem o próprio `<dialog>` como alvo: o conteúdo está em
        // elementos filhos, então comparar o alvo separa "clicou fora" de "clicou
        // dentro" sem uma camada extra só para capturar o clique.
        onClick={(evento) => {
          if (evento.target === dialogo.current) dialogo.current?.close();
        }}
      >
        <header className="flex items-start gap-3 px-5 py-4 border-b border-borda">
          <span className="flex items-center justify-center w-8 h-8 rounded-controle bg-acento-suave text-acento shrink-0">
            <Icone nome="info" tamanho="medio" />
          </span>
          <div className="min-w-0">
            <h2 id="titulo-sobre-a-tela" className="text-titulo-cartao">
              {titulo}
            </h2>
            <p className="text-nota text-tinta-secundaria mt-0.5">{descricao}</p>
          </div>
        </header>

        {/* O navegador torna áreas roláveis focáveis por teclado, para que se possa rolar
            com as setas, e é aqui que o foco pousa ao abrir. A classe `foco` existe para
            que o anel seja o do design system, e não o padrão do agente de usuário. */}
        <div className="foco max-h-[var(--altura-dialogo)] overflow-y-auto px-5 py-4">
          {secoes.map((secao) => (
            <section key={secao.rotulo} className="mb-5 last:mb-0">
              {/* Rótulo e fio, como as demais divisões do produto: o fio ocupa a
                  largura que sobra e amarra a seção sem pedir uma cor própria. */}
              <div className="flex items-center gap-3 mb-3">
                <p className="rotulo text-tinta-suave shrink-0">{secao.rotulo}</p>
                <span className="h-px flex-1 bg-borda" />
              </div>

              {secao.itens.map((item) => (
                <Item key={item.titulo} {...item} />
              ))}
            </section>
          ))}
        </div>

        <div className="flex justify-end bg-rodape border-t border-borda px-5 py-3">
          <Botao variante="primario" onClick={() => dialogo.current?.close()}>
            Entendi
          </Botao>
        </div>
      </dialog>
    </>
  );
}

function Item({ titulo, descricao, icone = "chevron_right", tom = "acento", nota }: ItemDeInfo) {
  return (
    <div className="flex items-start gap-3 mb-3 last:mb-0">
      <span
        className={`flex items-center justify-center w-8 h-8 rounded-controle shrink-0 ${TONS[tom]}`}
      >
        <Icone nome={icone} tamanho="pequeno" />
      </span>
      <div className="min-w-0">
        <p className="text-corpo font-semibold text-tinta">{titulo}</p>
        <p className="text-nota text-tinta-secundaria">{descricao}</p>
        {nota && (
          <p className="flex items-center gap-1 text-nota font-medium text-alerta-texto mt-1">
            <Icone nome="warning" tamanho="pequeno" />
            {nota}
          </p>
        )}
      </div>
    </div>
  );
}
