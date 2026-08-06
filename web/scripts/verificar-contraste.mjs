/**
 * Reprova pares de cor que não atendem ao contraste mínimo da WCAG 2.1 AA.
 *
 * Lê os valores do próprio `index.css`, para que a medição não continue valendo depois
 * de a paleta mudar.
 *
 * Mínimos aplicados:
 *   4,5:1  texto abaixo de 18,66px, ou abaixo de 14px em negrito
 *   3,0:1  texto grande e elemento gráfico não textual (preenchimento, borda de foco)
 *
 * Uso:  node scripts/verificar-contraste.mjs
 */

import { readFileSync } from "node:fs";

const RAIZ = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const css = readFileSync(`${RAIZ}src/index.css`, "utf8");

/** Lê um token de cor do CSS. */
function cor(token) {
  const achado = css.match(new RegExp(`${token}:\\s*(#[0-9a-fA-F]{6})`));
  if (!achado) throw new Error(`Token de cor ausente em index.css: ${token}`);
  return achado[1];
}

function luminancia(hex) {
  const canais = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = canais.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function razao(a, b) {
  const [maior, menor] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (maior + 0.05) / (menor + 0.05);
}

/**
 * Os pares que de fato ocorrem na interface, escritos à mão: uma varredura automática
 * de classes produziria combinações que nunca acontecem e deixaria passar as que
 * acontecem por composição.
 */
const PARES = [
  // Texto comum
  ["corpo sobre superfície", "--color-tinta-secundaria", "--color-superficie", 4.5],
  ["título sobre superfície", "--color-tinta", "--color-superficie", 4.5],
  ["nota sobre superfície", "--color-tinta-suave", "--color-superficie", 4.5],
  ["nota sobre fundo", "--color-tinta-suave", "--color-fundo", 4.5],
  ["rodapé de cartão", "--color-tinta-secundaria", "--color-rodape", 4.5],
  ["balão do usuário", "--color-tinta-secundaria", "--color-ativo", 4.5],

  // Status em texto — o degrau escuro, não a cor de gráfico
  ["pílula coberta", "--color-sucesso-texto", "--color-sucesso-suave", 4.5],
  ["pílula sem procedimento", "--color-alerta-texto", "--color-alerta-suave", 4.5],
  ["nota de OCR", "--color-alerta-texto", "--color-superficie", 4.5],
  ["pílula crítica", "--color-critico", "--color-critico-suave", 4.5],
  ["erro sobre superfície", "--color-critico", "--color-superficie", 4.5],

  // Preenchimentos cromáticos
  ["botão primário", "--color-tinta-invertida", "--color-acento", 4.5],
  ["item corrente da lateral", "--color-tinta-invertida", "--color-lateral-acento", 4.5],

  // A lateral escura
  ["item inativo da lateral", "--color-lateral-tinta-suave", "--color-lateral", 4.5],
  ["rótulo de seção", "--color-lateral-tinta-suave", "--color-lateral", 4.5],
  ["texto sobre elevada", "--color-lateral-tinta", "--color-lateral-elevada", 4.5],
  ["contagem de pendentes", "--color-lateral-alerta", "--color-lateral-elevada", 4.5],

  // Marcas não textuais: o mínimo é 3:1
  ["marca verde em gráfico", "--color-sucesso", "--color-superficie", 3],
  ["marca âmbar em gráfico", "--color-alerta", "--color-superficie", 3],
  ["marca do acento em gráfico", "--color-acento", "--color-superficie", 3],
  ["bloco do item corrente", "--color-lateral-acento", "--color-lateral", 3],
];

/**
 * Separações entre superfícies. Critério diferente do da WCAG, que mede texto contra o
 * que está atrás dele e nada diz sobre o cartão se destacar da página.
 *
 * O mínimo de 1,05 não vem de norma: é o degrau abaixo do qual, nesta paleta, a
 * diferença some em projetor. Existe para que mexer num degrau não apague outro.
 */
const SEPARACOES = [
  ["cartão sobre a página", "--color-superficie", "--color-fundo", 1.05],
  ["realce de passagem sobre a página", "--color-ativo", "--color-fundo", 1.05],
  ["item selecionado dentro do cartão", "--color-ativo", "--color-superficie", 1.05],
  ["borda sobre o cartão", "--color-borda", "--color-superficie", 1.05],
];

const falhas = [];
const linhas = [];

for (const [nome, frente, fundo, minimo] of PARES) {
  const valor = razao(cor(frente), cor(fundo));
  const passou = valor >= minimo;
  if (!passou) falhas.push({ nome, frente, fundo, valor, minimo });
  linhas.push(
    `  ${passou ? "ok     " : "REPROVA"} ${valor.toFixed(2).padStart(5)} : 1  (min ${minimo})  ${nome}`,
  );
}

console.log(`\nContraste WCAG 2.1 AA — ${PARES.length} pares\n`);
console.log(linhas.join("\n"));

const separacoes = [];
for (const [nome, frente, fundo, minimo] of SEPARACOES) {
  const valor = razao(cor(frente), cor(fundo));
  const passou = valor >= minimo;
  if (!passou) falhas.push({ nome, frente, fundo, valor, minimo });
  separacoes.push(
    `  ${passou ? "ok     " : "REPROVA"} ${valor.toFixed(3).padStart(5)} : 1  (min ${minimo})  ${nome}`,
  );
}

console.log(`\nSeparação entre superfícies — ${SEPARACOES.length} pares\n`);
console.log(separacoes.join("\n"));

if (falhas.length === 0) {
  console.log("\nNenhuma reprovação.\n");
  process.exit(0);
}

console.error(`\n${falhas.length} par(es) abaixo do mínimo:\n`);
for (const f of falhas) {
  console.error(`  ${f.nome}`);
  console.error(
    `    ${f.frente} (${cor(f.frente)}) sobre ${f.fundo} (${cor(f.fundo)})` +
      ` = ${f.valor.toFixed(2)}, mínimo ${f.minimo}\n`,
  );
}
process.exit(1);
