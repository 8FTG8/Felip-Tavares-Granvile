# Análise

Três notebooks, cada um sustentando uma decisão registrada em
[`docs/decisoes.md`](../docs/decisoes.md). Todos trazem as saídas gravadas — abrem legíveis
no GitHub, sem instalar nada — e todos reexecutam do zero sobre `docs/dados/banner.csv`,
versionado no repositório.

| | Sustenta | Custo de execução |
| --- | --- | --- |
| [`01-classificador-e-vazamento`](01-classificador-e-vazamento.ipynb) | ADR-003 — por que não há classificador no caminho crítico | ~10 min |
| [`02-calibracao-do-limiar`](02-calibracao-do-limiar.ipynb) | ADR-010 e ADR-010-A — de onde vem o número 0,8400 | ~1 min |
| [`03-analise-exploratoria`](03-analise-exploratoria.ipynb) | ADR-005, 006, 007 e 011 — o que os dados são | ~1 min |

Ler nesta ordem inverte a cronologia: o **03** é o que foi feito primeiro, e é por onde
começar quem não conhece o problema. O **01** é o que a entrevista cobra.

Nenhum número aparece escrito no texto dos notebooks. Todas as afirmações remetem à saída
de uma célula, para que uma reexecução que produza outro valor não deixe o documento
mentindo — a mesma regra que o ADR-017 registrou depois de a interface afirmar sobre os
dados algo que os dados não sustentavam.
