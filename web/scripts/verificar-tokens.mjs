/**
 * Reprova valores de estilo escritos fora do design system.
 *
 * Um design system que existe só na intenção volta a se dissolver na primeira
 * pressa — foi assim que a interface chegou a vinte e duas medidas de texto
 * distintas. Este verificador transforma a regra em condição de build: roda no
 * `npm run build` e falha antes de gerar o pacote.
 *
 * O que é aceito no ponto de uso:
 *   • utilitários gerados a partir de `@theme` (`text-corpo`, `rounded-cartao`);
 *   • arbitrários que citam um token (`w-[var(--largura-lateral)]`);
 *   • arbitrários percentuais e frações de grade, que são relação e não medida
 *     (`max-w-[85%]`, `grid-cols-[3fr_2fr]`).
 *
 * O que é reprovado: medida absoluta, cor literal, estilo passado como número a um
 * gráfico, opacidade fora dos dois degraus, z-index solto — e, na outra direção,
 * token declarado que ninguém consome.
 *
 * Uso:  node scripts/verificar-tokens.mjs
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const RAIZ = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const FONTE = join(RAIZ, "src");

/** O arquivo de tokens é onde os valores crus devem estar — é a definição deles. */
const DEFINICOES = ["src/index.css"];
/**
 * A ponte com o JavaScript lê os tokens do documento; nomeia-os, não os repete.
 * É o único arquivo autorizado a passar número a uma propriedade de estilo.
 */
const PONTES = ["src/estilo.ts"];

const REGRAS = [
  {
    nome: "medida absoluta em utilitário arbitrário",
    // `algo-[…]` cujo conteúdo não é token, percentual nem fração de grade. O hífen
    // antes do colchete é o que distingue um utilitário do Tailwind de um índice de
    // vetor em JavaScript — `payload[0]` não é decisão de estilo.
    padrao: /[a-z]-\[(?![^\]]*var\(--)(?![^\]]*%)(?![^\]]*fr[\s_\]])[^\]]*\d[^\]]*\]/g,
    dica: "declare um token em index.css e cite-o: w-[var(--largura-lateral)]",
  },
  {
    nome: "cor literal",
    padrao: /#[0-9a-fA-F]{3,8}\b|\brgba?\(/g,
    dica: "use um token de cor: var(--color-acento) ou a classe bg-acento",
    excetuar: PONTES,
  },
  {
    nome: "cor absoluta",
    // `white` ignora a rampa: a lateral é escura e o conteúdo é claro, então uma cor
    // absoluta acerta um dos dois por acaso.
    padrao: /\b(?:text|bg|border)-(?:white|black)\b/g,
    dica: "use tinta-invertida, superfície ou os tokens da lateral",
  },
  {
    nome: "medida de gráfico em número",
    // O Recharts recebe estilo como número em JavaScript, e nenhuma verificação de
    // classes alcança isso: foi por aqui que barSize, strokeWidth, largura de eixo e
    // opacidade de área voltaram a ser escritos no ponto de uso.
    padrao:
      /\b(?:fontSize|barSize|strokeWidth|minTickGap|stopOpacity|barGap|barCategoryGap|innerRadius|outerRadius)[:=]\s*\{?\s*-?[\d.]/g,
    dica: "use as medidas de componentes/graficos, que leem o degrau do CSS",
    excetuar: PONTES,
  },
  {
    nome: "margem de gráfico escrita no local",
    // Escritas no local, cada página negocia a sua e o alinhamento entre cartões
    // vizinhos se perde.
    padrao: /margin=\{\{/g,
    dica: "use MARGEM.serie, MARGEM.categorias ou MARGEM.compacto",
    excetuar: PONTES,
  },
  {
    nome: "opacidade fora dos dois degraus",
    // 25 para preenchimento ou borda derivados de status; 45 para véu, anel de foco
    // e elemento desabilitado. A revisão encontrou seis valores em uso — /20, /25,
    // /30, /40, /45, /50 —, nenhum distinguível do vizinho a olho nu.
    padrao: /\b(?:opacity-|(?:bg|text|border|ring|fill|stroke)-[\w-]+\/)(?!25\b|45\b)\d{1,3}\b/g,
    dica: "os degraus são 25 e 45 — veja a seção Opacidade em index.css",
  },
  {
    nome: "z-index em número solto",
    // Números soltos de empilhamento são a dívida de estilo clássica: quem chega
    // depois escreve 9999 porque não sabe contra o que está competindo.
    padrao: /\bz-\d+\b/g,
    dica: "use z-[var(--camada-barra)], --camada-veu ou --camada-gaveta",
  },
  {
    nome: "peso tipográfico fora dos quatro sancionados",
    // 400 corpo · 500 texto funcional · 600 títulos e ênfase · 700 destaque e marca.
    // Cada degrau da escala já declara o seu; escrever um peso é dar ênfase dentro do
    // degrau, e para isso quatro bastam.
    padrao: /font-(?!normal|medium|semibold|bold|sans|mono)[a-z]+/g,
    dica: "os pesos são normal, medium, semibold e bold — veja Tipografia em index.css",
  },
  {
    nome: "escala de cor do Tailwind",
    // A paleta do produto é fechada; um `slate-400` é uma quinta cor entrando pela
    // porta dos fundos.
    padrao:
      /\b(?:text|bg|border|ring|fill|stroke|from|to|via)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/g,
    dica: "a paleta é fechada: acento, sucesso, alerta, crítico e a rampa de tinta",
  },
];

function arquivos(diretorio) {
  return readdirSync(diretorio).flatMap((nome) => {
    const caminho = join(diretorio, nome);
    if (statSync(caminho).isDirectory()) return arquivos(caminho);
    return /\.(tsx?|css)$/.test(nome) ? [caminho] : [];
  });
}

const relativo = (caminho) => relative(RAIZ, caminho).replace(/\\/g, "/");

/* ── Valores crus no ponto de uso ────────────────────────────────────────────── */

const achados = [];

for (const caminho of arquivos(FONTE)) {
  const parente = relativo(caminho);
  if (DEFINICOES.includes(parente)) continue;

  const linhas = readFileSync(caminho, "utf8").split("\n");

  for (const regra of REGRAS) {
    if (regra.excetuar?.includes(parente)) continue;

    linhas.forEach((linha, indice) => {
      // Comentários descrevem o problema; não são o problema.
      const codigo = linha.replace(/\/\/.*$/, "").replace(/\/\*.*?\*\//g, "");
      if (/^\s*\*/.test(linha)) return;

      for (const achado of codigo.matchAll(regra.padrao)) {
        achados.push({
          arquivo: parente,
          linha: indice + 1,
          trecho: achado[0].trim(),
          regra: regra.nome,
          dica: regra.dica,
        });
      }
    });
  }
}

/* ── Tokens declarados e nunca consumidos ────────────────────────────────────── */

/**
 * Um token morto é tão danoso quanto um valor cru: significa que a decisão está
 * registrada num lugar e o produto obedece a outro. Foi exatamente assim que a
 * escala tipográfica original ficou declarada em `index.css` sem que um único
 * componente a usasse — o CSS afirmava sete degraus e a tela tinha vinte e dois.
 */
const css = readFileSync(join(RAIZ, DEFINICOES[0]), "utf8");
const fonte = arquivos(FONTE)
  .filter((caminho) => !DEFINICOES.includes(relativo(caminho)))
  .map((caminho) => readFileSync(caminho, "utf8"))
  .join("\n");

// O corpo do CSS fora do bloco @theme também conta como uso.
const corpoCss = css.slice(css.indexOf("@layer base"));

const mortos = [];
for (const [, token] of css.matchAll(/^\s*(--[\w-]+):/gm)) {
  // Modificadores pertencem ao degrau que acompanham.
  if (/--(?:line-height|letter-spacing|font-weight)$/.test(token)) continue;
  // Variáveis que o próprio Tailwind consome, sem serem citadas por nome.
  if (token.startsWith("--default-")) continue;

  // `--color-acento` vira a classe `acento`; `--breakpoint-projetor` vira o prefixo
  // de variante `projetor:`; `--largura-lateral` é citado inteiro dentro de `var()`.
  const utilitario = token
    .replace(/^--(?:color|text|radius|shadow|font|breakpoint)-/, "")
    .replace(/^--/, "");
  const citado =
    fonte.includes(token) ||
    corpoCss.includes(token) ||
    new RegExp(`[-:\\s"'\`\\[]${utilitario}\\b`).test(fonte);

  if (!citado) mortos.push(token);
}

/* ── Relatório ───────────────────────────────────────────────────────────────── */

if (achados.length === 0 && mortos.length === 0) {
  console.log("Tokens: nenhum valor de estilo fora do design system, nenhum token morto.");
  process.exit(0);
}

if (achados.length) {
  console.error(`\nValores de estilo fora do design system (${achados.length}):\n`);
  for (const achado of achados) {
    console.error(`  ${achado.arquivo}:${achado.linha}  ${achado.trecho}`);
    console.error(`    ${achado.regra} — ${achado.dica}\n`);
  }
}

if (mortos.length) {
  console.error(`\nTokens declarados e nunca usados (${mortos.length}):\n`);
  for (const token of mortos) {
    console.error(`  src/index.css  ${token}`);
    console.error("    apague-o ou consuma-o — decisão registrada e não obedecida\n");
  }
}

process.exit(1);
