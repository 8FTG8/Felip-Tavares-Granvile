/**
 * Peças visuais reaproveitadas pelas telas.
 *
 * Escritas à mão, sem biblioteca de componentes: são poucas, cabem em um arquivo e
 * cada decisão de estilo pode ser justificada. A alternativa — importar um kit
 * pronto — traria dezenas de variantes que o projeto não usa.
 *
 * Nenhum valor de estilo é escrito aqui: tamanho, raio, cor e sombra vêm dos tokens
 * de `index.css`. É este arquivo, e não o CSS, que o verificador de tokens mais
 * protege — componentes compartilhados são onde uma medida solta se multiplica.
 */

import { useRef } from "react";
import type { ReactNode } from "react";

import { numero } from "../formato";
import { useDecorrido } from "../tempo";

/* ── Superfícies ─────────────────────────────────────────────────────────────── */

export function Cartao({
  titulo,
  complemento,
  acao,
  rodape,
  children,
  className = "",
  semPadding = false,
}: {
  titulo?: string;
  complemento?: string;
  acao?: ReactNode;
  rodape?: ReactNode;
  children: ReactNode;
  className?: string;
  semPadding?: boolean;
}) {
  return (
    // A separação vem da borda, e só dela: o cartão é branco sobre um fundo 1% mais
    // escuro, com um fio de 1px. Havia aqui uma sombra a 3% de opacidade — invisível, e
    // por isso mesmo indefensável: dizia ao mesmo tempo "separo por borda" e "mas por
    // via das dúvidas". Foi apagada com o token.
    <section
      className={`bg-superficie border border-borda rounded-cartao ${
        rodape ? "overflow-hidden" : ""
      } ${className}`}
    >
      <div className={semPadding ? "" : "p-4 sm:p-5"}>
        {titulo && (
          <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1 mb-4">
            <h2 className="text-titulo-cartao text-tinta">{titulo}</h2>
            {complemento && <span className="text-nota text-tinta-suave">{complemento}</span>}
            {acao && <div className="ml-auto">{acao}</div>}
          </header>
        )}
        {children}
      </div>
      {rodape}
    </section>
  );
}

/**
 * Faixa de ação no pé do cartão.
 *
 * Separa a leitura do dado do que se pode fazer com ele: o número fica na superfície
 * branca, a ação numa faixa levemente rebaixada. O rótulo em caixa alta e a seta
 * diagonal marcam que aquilo leva para outro lugar da aplicação, não abre um menu.
 */
export function RodapeCartao({ rotulo, onClick }: { rotulo: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="foco w-full flex items-center gap-2 bg-rodape border-t border-borda px-4 sm:px-5 py-3 rotulo text-tinta-secundaria hover:text-acento hover:bg-ativo transition"
    >
      {rotulo}
      <Icone nome="arrow_outward" tamanho="pequeno" className="ml-auto" />
    </button>
  );
}

/* ── Metadados ───────────────────────────────────────────────────────────────── */

export function Etiqueta({ children, cor }: { children: ReactNode; cor?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-nota text-tinta-secundaria bg-fundo border border-borda rounded-full px-2.5 py-1 whitespace-nowrap">
      {cor && <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: cor }} />}
      {children}
    </span>
  );
}

/** Pílula de estado, sempre com rótulo — a cor nunca informa sozinha. */
export function Pilula({
  texto,
  tom,
}: {
  texto: string;
  tom: "sucesso" | "alerta" | "critico" | "neutro";
}) {
  const tons = {
    sucesso: "text-sucesso-texto bg-sucesso-suave border-sucesso/25",
    alerta: "text-alerta-texto bg-alerta-suave border-alerta/25",
    critico: "text-critico bg-critico-suave border-critico/25",
    neutro: "text-tinta-secundaria bg-fundo border-borda",
  } as const;

  return (
    <span
      className={`inline-flex items-center justify-center rotulo border rounded-sutil px-2 py-0.5 ${tons[tom]}`}
    >
      {texto}
    </span>
  );
}

/* ── Ações ───────────────────────────────────────────────────────────────────── */

export function Botao({
  children,
  onClick,
  variante = "secundario",
  disabled,
  icone,
  className = "",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variante?: "primario" | "secundario" | "sutil";
  disabled?: boolean;
  icone?: string;
  className?: string;
  type?: "button" | "submit";
}) {
  const variantes = {
    // A sombra deriva do próprio acento por `color-mix`: concatenar opacidade em
    // hexadecimal produziria `var(--color-acento)35`, que o navegador descarta.
    primario:
      "bg-acento text-tinta-invertida border-acento hover:brightness-110 shadow-[0_1px_4px_color-mix(in_srgb,var(--color-acento)_35%,transparent)]",
    secundario:
      "bg-superficie text-tinta-secundaria border-borda hover:bg-fundo hover:text-tinta",
    sutil: "bg-transparent text-tinta-secundaria border-transparent hover:bg-ativo",
  } as const;

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`foco inline-flex items-center justify-center gap-2 text-corpo font-medium border rounded-controle px-4 py-2 transition disabled:opacity-45 disabled:cursor-not-allowed ${variantes[variante]} ${className}`}
    >
      {icone && <Icone nome={icone} tamanho="medio" />}
      {children}
    </button>
  );
}

/**
 * Controle segmentado: um conjunto fechado de opções, todas visíveis.
 *
 * Preferido a um `<select>` quando o número de opções é pequeno e **o fato de serem
 * exaustivas é a informação**. Um menu esconde a lista e obriga a abri-la para saber
 * o que existe; segmentado mostra o conjunto inteiro de uma vez.
 *
 * As opções são deliberadamente neutras, sem cor por opção: onde este controle é
 * usado, colorir cada botão pelo resultado que ele produz anunciaria a resposta antes
 * de o sistema a calcular.
 */
export function Segmentado<T extends string | number>({
  valor,
  aoMudar,
  opcoes,
  rotulo,
}: {
  valor: T;
  aoMudar: (valor: T) => void;
  opcoes: { valor: T; rotulo: string; descricao?: string }[];
  rotulo: string;
}) {
  const grupo = useRef<HTMLDivElement>(null);

  /**
   * Navegação por setas, como um grupo de rádio exige.
   *
   * A versão anterior declarava `role="radiogroup"` e não implementava nada disso: um
   * leitor de tela anunciava "grupo de opções, 1 de 4", a pessoa apertava a seta e não
   * acontecia nada. Semântica prometida e não cumprida é pior que semântica ausente —
   * a ausente ao menos não instrui a fazer o que não funciona.
   *
   * Também é útil a quem enxerga: durante a apresentação, alternar entre os quatro
   * casos vira duas teclas em vez de quatro cliques.
   */
  function aoTeclar(evento: React.KeyboardEvent, indice: number) {
    const passo = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[evento.key];
    if (passo === undefined) return;
    evento.preventDefault();
    const destino = (indice + passo + opcoes.length) % opcoes.length;
    aoMudar(opcoes[destino].valor);
    grupo.current?.querySelectorAll("button")[destino]?.focus();
  }

  return (
    <div
      ref={grupo}
      role="radiogroup"
      aria-label={rotulo}
      className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4"
    >
      {opcoes.map((opcao, indice) => {
        const ativo = opcao.valor === valor;
        return (
          <button
            key={opcao.valor}
            role="radio"
            aria-checked={ativo}
            // Tabulação itinerante: o grupo inteiro é uma parada só, e as setas
            // percorrem as opções. Quatro paradas seguidas fariam o teclado atravessar
            // o controle em vez de operá-lo.
            tabIndex={ativo ? 0 : -1}
            onKeyDown={(evento) => aoTeclar(evento, indice)}
            onClick={() => aoMudar(opcao.valor)}
            className={`foco text-left border rounded-controle px-3 py-2.5 transition ${
              ativo
                ? "border-acento bg-acento-suave"
                : "border-borda bg-superficie hover:bg-fundo hover:border-tinta-suave"
            }`}
          >
            <span
              className={`block text-corpo font-semibold ${
                ativo ? "text-acento" : "text-tinta"
              }`}
            >
              {opcao.rotulo}
            </span>
            {opcao.descricao && (
              <span className="block text-nota text-tinta-secundaria">{opcao.descricao}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Ícone em traço.
 *
 * O tamanho vem da escala tipográfica, e não de um número: o ícone acompanha o
 * texto ao lado do qual aparece, então medi-lo em outra régua fazia com que cada
 * ajuste de fonte exigisse um ajuste manual de ícone que ninguém lembrava de fazer.
 *
 * A fonte Material Symbols renderiza o nome do ícone como ligadura, o que significa
 * que o texto "play_arrow" está de fato no documento. Sem `aria-hidden`, o leitor de
 * tela o anuncia junto do rótulo do botão — "play_arrow Analisar evento".
 */
export function Icone({
  nome,
  tamanho = "medio",
  className = "",
}: {
  nome: string;
  tamanho?: "pequeno" | "medio" | "grande" | "vazio";
  className?: string;
}) {
  const tamanhos = {
    pequeno: "text-corpo-forte",
    medio: "text-titulo-cartao",
    grande: "text-titulo-pagina",
    vazio: "text-destaque",
  } as const;

  return (
    <span
      aria-hidden="true"
      className={`material-symbols-outlined leading-none shrink-0 ${tamanhos[tamanho]} ${className}`}
    >
      {nome}
    </span>
  );
}

/* ── Estados de tela ─────────────────────────────────────────────────────────── */

export function Vazio({
  icone,
  titulo,
  descricao,
}: {
  icone: string;
  titulo: string;
  descricao: string;
}) {
  return (
    <div className="text-center py-12 text-tinta-suave">
      <Icone nome={icone} tamanho="vazio" className="opacity-45" />
      <p className="mt-3 text-corpo-forte text-tinta-secundaria">{titulo}</p>
      <p className="mt-1 text-corpo max-w-sm mx-auto">{descricao}</p>
    </div>
  );
}

/**
 * Espera em andamento.
 *
 * Com `contarTempo`, exibe os segundos decorridos e, passados alguns deles, explica por
 * que a espera é longa. Não é enfeite: a geração leva dezenas de segundos em estação sem
 * GPU dedicada, e um indicador mudo é indistinguível de um sistema travado — na sala de
 * apresentação, os dois se parecem exatamente igual.
 *
 * A explicação não afirma em que hardware está rodando, porque a interface não sabe: diz
 * qual é a condição que produz a demora e deixa a conclusão para quem apresenta.
 */
export function Carregando({
  texto,
  contarTempo = false,
}: {
  texto: string;
  contarTempo?: boolean;
}) {
  const segundos = useDecorrido(contarTempo);

  return (
    <div role="status" aria-live="polite" className="text-tinta-secundaria text-corpo py-6">
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="w-4 h-4 border-2 border-borda border-t-acento rounded-full animate-spin"
        />
        {texto}
        {contarTempo && segundos > 0 && (
          <span className="tabular text-nota text-tinta-suave">{segundos}s</span>
        )}
      </div>
      {contarTempo && segundos >= 8 && (
        <p className="text-nota text-tinta-suave mt-2 ml-7">
          A redação da prescrição roda no modelo local. Sem GPU dedicada, leva dezenas de
          segundos; na estação de 16 GB de VRAM prevista para operação, segundos.
        </p>
      )}
    </div>
  );
}

export function AvisoApi() {
  return (
    <Cartao className="border-critico/25">
      <div className="flex gap-3">
        <Icone nome="cloud_off" className="text-critico" />
        <div className="text-corpo">
          <p className="font-semibold text-tinta">A API não está respondendo.</p>
          <p className="text-tinta-secundaria mt-1">
            A interface é apenas um cliente do serviço — em ambiente industrial o consumidor
            principal seria o supervisório. Suba a API antes de continuar:
          </p>
          <code className="block mt-2 bg-fundo border border-borda rounded-sutil px-3 py-2">
            uvicorn src.api.app:app
          </code>
        </div>
      </div>
    </Cartao>
  );
}

/**
 * Aviso de que o serviço de modelos está fora do ar.
 *
 * Separado de :func:`AvisoApi` porque a ação corretiva é outra, e a mensagem antiga
 * mandava reiniciar a API — que estava no ar o tempo todo.
 *
 * O segundo parágrafo não é consolo: com o modelo derrubado, as duas barreiras do
 * guardrail continuam ativas e três dos quatro caminhos seguem respondendo, porque os
 * textos de recusa são compostos em código e nunca gerados. Dizer isso na tela
 * transforma a falha em demonstração da arquitetura.
 */
export function AvisoModelo({ detalhe }: { detalhe?: string }) {
  return (
    <Cartao className="border-alerta/25">
      <div className="flex gap-3">
        <Icone nome="cloud_off" className="text-alerta-texto" />
        <div className="text-corpo">
          <p className="font-semibold text-tinta">
            O serviço de modelos não está respondendo.
          </p>
          <p className="text-tinta-secundaria mt-1">
            {detalhe ?? "A API está no ar; quem não respondeu foi o Ollama."} As
            verificações documentais seguem ativas — o sistema continua identificando a
            condição, consultando o histórico e <strong>recusando</strong> o que não tem
            respaldo. Só não consegue redigir a prescrição.
          </p>
          <code className="block mt-2 bg-fundo border border-borda rounded-sutil px-3 py-2">
            ollama serve
          </code>
        </div>
      </div>
    </Cartao>
  );
}

/* ── Campos de formulário ────────────────────────────────────────────────────── */

const CAMPO =
  "foco w-full text-corpo bg-superficie border border-borda rounded-controle px-3 py-2 transition focus:border-acento";

/** Rótulo associado ao controle por `id`, para que o leitor de tela o anuncie. */
export function Campo({
  id,
  rotulo,
  auxilio,
  children,
  className = "",
}: {
  id: string;
  rotulo: string;
  auxilio?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={id} className="block text-nota font-medium text-tinta-secundaria mb-1.5">
        {rotulo}
      </label>
      {children}
      {auxilio && <p className="text-nota text-tinta-suave mt-1.5">{auxilio}</p>}
    </div>
  );
}

export function Selecao({
  id,
  valor,
  aoMudar,
  opcoes,
}: {
  id: string;
  valor: string | number;
  aoMudar: (valor: string) => void;
  opcoes: { valor: string | number; rotulo: string }[];
}) {
  return (
    <select
      id={id}
      value={valor}
      onChange={(evento) => aoMudar(evento.target.value)}
      className={CAMPO}
    >
      {opcoes.map((opcao) => (
        <option key={opcao.valor} value={opcao.valor}>
          {opcao.rotulo}
        </option>
      ))}
    </select>
  );
}

export function Entrada({
  id,
  valor,
  aoMudar,
  placeholder,
  aoTeclar,
  desabilitado,
  className = "",
}: {
  id: string;
  valor: string;
  aoMudar: (valor: string) => void;
  placeholder?: string;
  aoTeclar?: (tecla: string) => void;
  desabilitado?: boolean;
  className?: string;
}) {
  return (
    <input
      id={id}
      value={valor}
      onChange={(evento) => aoMudar(evento.target.value)}
      onKeyDown={(evento) => aoTeclar?.(evento.key)}
      placeholder={placeholder}
      disabled={desabilitado}
      className={`${CAMPO} disabled:bg-fundo ${className}`}
    />
  );
}

/* ── Gráficos ────────────────────────────────────────────────────────────────── */

/**
 * Dica de gráfico.
 *
 * Definida aqui, e não em cada página, porque a dica padrão do Recharts traz fundo
 * branco fixo e sombra própria — valores que não passam pelos tokens e destoariam da
 * elevação quase nula do resto do sistema.
 */
export function Dica({
  active,
  payload,
  label,
  sufixo = "eventos",
}: {
  active?: boolean;
  payload?: { value: number; payload: Record<string, unknown> }[];
  label?: string;
  sufixo?: string;
}) {
  if (!active || !payload?.length) return null;
  const ponto = payload[0];
  const titulo = (ponto.payload.condicao as string) ?? label;

  return (
    <div className="bg-superficie border border-borda rounded-controle shadow-[var(--shadow-flutuante)] px-3 py-2">
      <p className="text-nota font-semibold text-tinta">{titulo}</p>
      <p className="text-nota text-tinta-secundaria">
        {numero(ponto.value)} {sufixo}
      </p>
    </div>
  );
}
