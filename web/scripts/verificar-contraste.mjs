/**
 * Reprova pares de cor que não atendem ao contraste mínimo da WCAG 2.1 AA.
 *
 * O cabeçalho do `index.css` afirma que as cores foram medidas. Uma afirmação dessas
 * ou é verificável ou não deveria estar escrita — e ela já esteve errada: a medição
 * original cobria a **separação ΔE entre marcas de gráfico sob daltonismo** e nunca o
 * **contraste de texto** sobre os fundos tingidos. Quatro pares reprovavam em
 * silêncio, três deles porque verde e âmbar foram escolhidos como marca de gráfico
 * (mínimo 3:1) e depois reaproveitados como texto (mínimo 4,5:1).
 *
 * Este verificador lê os valores do próprio `index.css`, então não há como a paleta
 * mudar e a medição continuar valendo para a paleta antiga.
 *
 * Mínimos aplicados (WCAG 2.1 AA):
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
 * Os pares que de fato ocorrem na interface.
 *
 * A lista é escrita à mão porque só quem conhece as telas sabe o que fica sobre o
 * quê — uma varredura automática de classes produziria combinações que nunca
 * acontecem e deixaria passar as que acontecem por composição.
 */
const PARES = [
  // Texto comum
  ["corpo sobre superfície", "--color-tinta-secundaria", "--color-superficie", 4.5],
  ["título sobre superfície", "--color-tinta", "--color-superficie", 4.5],
  ["nota sobre superfície", "--color-tinta-suave", "--color-superficie", 4.5],
  ["nota sobre fundo", "--color-tinta-suave", "--color-fundo", 4.5],
  ["rodapé de cartão", "--color-tinta-secundaria", "--color-rodape", 4.5],

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
