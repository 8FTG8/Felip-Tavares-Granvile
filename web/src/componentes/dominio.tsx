/**
 * Componentes que carregam significado do domínio.
 *
 * A apresentação dos três caminhos de resposta é o ponto sensível da interface: confundir
 * uma recusa com uma recomendação vazia faz o técnico perder a informação mais importante
 * que o sistema tem a dar. Por isso cada caminho recebe cor, ícone **e** rótulo, com uma
 * linha explicando o que aquilo significa.
 */

import { useState } from "react";
import type { Caminho, Fonte } from "../api/tipos";
import { Icone } from "./base";

const CAMINHOS: Record<
  Caminho,
  { icone: string; titulo: string; descricao: string; cor: string; fundo: string }
> = {
  prescricao: {
    icone: "task_alt",
    titulo: "Procedimento encontrado",
    descricao: "Recomendação fundamentada em documento técnico da empresa",
    cor: "var(--color-sucesso)",
    fundo: "var(--color-sucesso-suave)",
  },
  sem_documento: {
    icone: "report",
    titulo: "Sem procedimento cadastrado",
    descricao: "O sistema não emite recomendação sem respaldo documental",
    cor: "var(--color-alerta)",
    fundo: "var(--color-alerta-suave)",
  },
  estado: {
    icone: "check_circle",
    titulo: "Equipamento sem defeito",
    descricao: "O evento registra um estado operacional, não uma falha",
    cor: "var(--color-acento)",
    fundo: "var(--color-acento-suave)",
  },
  sem_condicao: {
    icone: "help",
    titulo: "Condição não informada",
    descricao: "Sem a condição não há como saber qual procedimento responde",
    cor: "var(--color-tinta-secundaria)",
    fundo: "var(--color-ativo)",
  },
};

export function SeloCaminho({
  caminho,
  documento,
  compacto = false,
}: {
  caminho: Caminho;
  documento?: string | null;
  compacto?: boolean;
}) {
  const aparencia = CAMINHOS[caminho] ?? CAMINHOS.sem_condicao;

  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-borda bg-superficie px-4 py-3"
      style={{ borderLeft: `3px solid ${aparencia.cor}` }}
    >
      <span
        className="flex items-center justify-center w-7 h-7 rounded-full shrink-0"
        style={{ background: aparencia.fundo, color: aparencia.cor }}
      >
        <Icone nome={aparencia.icone} tamanho={17} />
      </span>
      <div className="leading-tight min-w-0">
        <p className="font-semibold text-tinta text-[0.88rem]">{aparencia.titulo}</p>
        {!compacto && (
          <p className="text-[0.78rem] text-tinta-secundaria mt-0.5">{aparencia.descricao}</p>
        )}
      </div>
      {documento && (
        <code className="ml-auto text-[0.72rem] text-tinta-secundaria bg-fundo border border-borda rounded-full px-2.5 py-1">
          {documento}
        </code>
      )}
    </div>
  );
}

/**
 * Seções que fundamentam a recomendação.
 *
 * A rastreabilidade é requisito, não enfeite: o técnico precisa poder abrir o procedimento
 * citado e conferir. Documentos transcritos por OCR são marcados, porque o reconhecimento
 * pode conter ruído.
 */
export function Fontes({ fontes }: { fontes: Fonte[] }) {
  const [aberto, setAberto] = useState(false);
  if (!fontes.length) return null;

  return (
    <div className="mt-4 border border-borda rounded-lg overflow-hidden">
      <button
        onClick={() => setAberto(!aberto)}
        aria-expanded={aberto}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-[0.82rem] font-medium text-tinta-secundaria hover:bg-fundo transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-acento/40"
      >
        <Icone nome="menu_book" tamanho={17} />
        Fontes citadas ({fontes.length})
        <Icone nome={aberto ? "expand_less" : "expand_more"} tamanho={18} className="ml-auto" />
      </button>

      {aberto && (
        <ul className="border-t border-borda">
          {fontes.map((fonte) => (
            <li
              key={`${fonte.documento}-${fonte.numero_secao}`}
              className="px-4 py-3 border-b border-borda last:border-0"
            >
              <p className="text-[0.84rem]">
                <span className="font-semibold text-tinta">
                  {fonte.documento}, seção {fonte.numero_secao}
                </span>
                <span className="text-tinta-secundaria"> — {fonte.titulo_secao}</span>
              </p>
              <p className="text-[0.74rem] text-tinta-suave mt-0.5">
                relevância {fonte.relevancia.toFixed(3)}
                {fonte.origem === "ocr" && (
                  <span className="text-alerta"> · transcrito por OCR</span>
                )}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Renderização mínima de markdown — negrito, itálico, código, listas e parágrafos.
 *
 * Suficiente para o que o modelo produz, e preferível a uma dependência de markdown
 * completa: o conteúdo vem de um prompt que pede passos numerados e citações, não
 * documentos arbitrários.
 */
export function Prosa({ texto }: { texto: string }) {
  // O escape vem antes de qualquer substituição, e as únicas tags geradas adiante são
  // fechadas e sem atributos — não há como o texto do modelo introduzir marcação.
  const html = texto
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .split(/\n{2,}/)
    .map((bloco) => {
      const linhas = bloco.split("\n").filter(Boolean);
      const numerada = linhas.every((l) => /^\s*\d+[.)]\s/.test(l));
      const marcada = linhas.every((l) => /^\s*[-*]\s/.test(l));
      if (numerada && linhas.length) {
        return `<ol>${linhas.map((l) => `<li>${l.replace(/^\s*\d+[.)]\s/, "")}</li>`).join("")}</ol>`;
      }
      if (marcada && linhas.length) {
        return `<ul>${linhas.map((l) => `<li>${l.replace(/^\s*[-*]\s/, "")}</li>`).join("")}</ul>`;
      }
      return `<p>${linhas.join("<br>")}</p>`;
    })
    .join("");

  return <div className="prosa" dangerouslySetInnerHTML={{ __html: html }} />;
}

export function RodapeModelo({ modelo }: { modelo: string | null }) {
  return (
    <p className="text-[0.74rem] text-tinta-suave mt-3">
      {modelo ? (
        <>
          Resposta redigida por <code>{modelo}</code> a partir dos trechos citados.
        </>
      ) : (
        "Resposta composta pelo sistema, sem geração por modelo de linguagem."
      )}
    </p>
  );
}
