/**
 * Peças visuais reaproveitadas pelas telas.
 *
 * Escritas à mão, sem biblioteca de componentes: são poucas, cabem em um arquivo e cada
 * decisão de estilo pode ser justificada. A alternativa — importar um kit pronto — traria
 * dezenas de variantes que o projeto não usa.
 */

import type { ReactNode } from "react";

/* ── Superfícies ─────────────────────────────────────────────────────────────── */

export function Cartao({
  titulo,
  complemento,
  acao,
  children,
  className = "",
  semPadding = false,
}: {
  titulo?: string;
  complemento?: string;
  acao?: ReactNode;
  children: ReactNode;
  className?: string;
  semPadding?: boolean;
}) {
  return (
    <section
      className={`bg-superficie border border-borda rounded-[12px] shadow-[var(--shadow-cartao)] ${
        semPadding ? "" : "p-5"
      } ${className}`}
    >
      {titulo && (
        <header className="flex items-baseline gap-3 mb-4">
          <h2 className="text-[1rem] font-semibold text-tinta">{titulo}</h2>
          {complemento && (
            <span className="text-xs text-tinta-suave">{complemento}</span>
          )}
          {acao && <div className="ml-auto">{acao}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

/* ── Metadados ───────────────────────────────────────────────────────────────── */

export function Etiqueta({
  children,
  cor,
}: {
  children: ReactNode;
  cor?: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[0.72rem] text-tinta-secundaria bg-fundo border border-borda rounded-full px-2.5 py-1 whitespace-nowrap">
      {cor && (
        <span
          className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ background: cor }}
        />
      )}
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
    sucesso: "text-sucesso bg-sucesso-suave border-sucesso/25",
    alerta: "text-alerta bg-alerta-suave border-alerta/25",
    critico: "text-critico bg-critico-suave border-critico/25",
    neutro: "text-tinta-secundaria bg-fundo border-borda",
  } as const;
  return (
    <span
      className={`inline-flex items-center justify-center text-[0.66rem] font-semibold uppercase tracking-wide border rounded px-2 py-1 ${tons[tom]}`}
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
    primario:
      "bg-acento text-white border-acento hover:brightness-110 shadow-[0_1px_4px_color-mix(in_srgb,var(--color-acento)_35%,transparent)]",
    secundario:
      "bg-superficie text-tinta-secundaria border-borda hover:bg-fundo hover:text-tinta",
    sutil: "bg-transparent text-tinta-secundaria border-transparent hover:bg-ativo",
  } as const;

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 text-[0.86rem] font-medium border rounded-lg px-4 py-2 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-acento focus-visible:ring-offset-2 focus-visible:ring-offset-fundo disabled:opacity-45 disabled:cursor-not-allowed ${variantes[variante]} ${className}`}
    >
      {icone && <Icone nome={icone} tamanho={18} />}
      {children}
    </button>
  );
}

/**
 * Ícone em traço.
 *
 * A fonte Material Symbols renderiza o nome do ícone como ligadura, o que significa que
 * o texto "play_arrow" está de fato no documento. Sem `aria-hidden`, o leitor de tela o
 * anuncia junto do rótulo do botão — "play_arrow Analisar evento".
 */
export function Icone({
  nome,
  tamanho = 20,
  className = "",
}: {
  nome: string;
  tamanho?: number;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={`material-symbols-outlined leading-none shrink-0 ${className}`}
      style={{ fontSize: tamanho }}
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
    <div className="text-center py-14 text-tinta-suave">
      <Icone nome={icone} tamanho={40} className="opacity-40" />
      <p className="mt-3 text-[0.92rem] font-medium text-tinta-secundaria">{titulo}</p>
      <p className="mt-1 text-[0.84rem] max-w-sm mx-auto leading-relaxed">{descricao}</p>
    </div>
  );
}

export function Carregando({ texto }: { texto: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-3 text-tinta-secundaria text-[0.86rem] py-6"
    >
      <span
        aria-hidden="true"
        className="w-4 h-4 border-2 border-borda border-t-acento rounded-full animate-spin"
      />
      {texto}
    </div>
  );
}

export function AvisoApi() {
  return (
    <Cartao className="border-critico/40">
      <div className="flex gap-3">
        <Icone nome="cloud_off" className="text-critico" />
        <div className="text-[0.88rem] leading-relaxed">
          <p className="font-semibold text-tinta">A API não está respondendo.</p>
          <p className="text-tinta-secundaria mt-1">
            A interface é apenas um cliente do serviço — em ambiente industrial o consumidor
            principal seria o supervisório. Suba a API antes de continuar:
          </p>
          <code className="block mt-2 bg-fundo border border-borda rounded px-3 py-2">
            uvicorn src.api.app:app
          </code>
        </div>
      </div>
    </Cartao>
  );
}

/* ── Formatação ──────────────────────────────────────────────────────────────── */

export const numero = (valor: number) => valor.toLocaleString("pt-BR");

/** Percentual para leitura humana — com vírgula decimal, como se escreve em português. */
export const percentual = (valor: number, casas = 1) =>
  `${(valor * 100).toFixed(casas).replace(".", ",")}%`;

/**
 * Percentual para uso em CSS.
 *
 * Existe separado de :func:`percentual` porque a vírgula decimal do português produz um
 * valor que o navegador descarta silenciosamente: `width: "80,4%"` não é CSS válido, e a
 * barra simplesmente não preenche.
 */
export const percentualCss = (valor: number) => `${(valor * 100).toFixed(1)}%`;

/* ── Campos de formulário ────────────────────────────────────────────────────── */

const CAMPO =
  "w-full text-[0.86rem] bg-superficie border border-borda rounded-lg px-3 py-2 transition focus:border-acento focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-acento/40";

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
      <label htmlFor={id} className="block text-[0.78rem] font-medium text-tinta-secundaria mb-1.5">
        {rotulo}
      </label>
      {children}
      {auxilio && <p className="text-[0.76rem] text-tinta-suave mt-1.5">{auxilio}</p>}
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
 * Definida aqui, e não em cada página, porque a dica padrão do Recharts traz fundo branco
 * fixo — no tema escuro ela apareceria como uma caixa clara sobre superfície escura.
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
    <div className="bg-superficie border border-borda rounded-lg shadow-[var(--shadow-flutuante)] px-3 py-2">
      <p className="text-[0.8rem] font-semibold text-tinta">{titulo}</p>
      <p className="text-[0.78rem] text-tinta-secundaria">
        {numero(ponto.value)} {sufixo}
      </p>
    </div>
  );
}
