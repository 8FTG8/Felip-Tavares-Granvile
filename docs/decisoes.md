# Registro de Decisões Técnicas

---

## ADR-001 — LLM local via Ollama

**Contexto.** A recomendação precisa ser redigida em linguagem natural, e a operação tem
de caber em estação comercial — 32 GB de RAM, GPU de 16 GB.

**Decisão.** Modelo de 7–8B quantizado, servido localmente por Ollama.

**Justificativa.** Chão de fábrica opera em rede segregada e dado de processo é sensível:
API externa criaria dependência de conectividade e exporia operação a terceiros.
Quantizado, o modelo ocupa 5–6 GB de VRAM e cabe junto com os embeddings. A qualidade
menor que a de um modelo de fronteira não pesa — o RAG entrega os trechos recuperados, e
ao modelo cabe só redigir.

---

## ADR-002 — API REST em FastAPI, com interface própria em React

**Contexto.** A entrega precisa de chat, painel e upload de documentos, e a integração em
ambiente industrial é critério de diferencial.

**Decisão.** FastAPI expondo a solução como API REST documentada. A interface é um cliente
HTTP em processo separado — React 19, Vite, TypeScript e Tailwind, em `web/` —, consumindo
exclusivamente os endpoints.

**Justificativa.** O consumidor natural em ambiente industrial não é uma pessoa num
navegador: é o supervisório, o CMMS ou o broker que recebe os eventos dos sensores. A API é
o contrato que torna essa integração possível; a interface é um cliente entre outros.

Streamlit foi a escolha inicial e caiu no uso — reexecuta o script a cada interação, o que
não comporta resposta transmitida em partes (a geração leva de 32 s a 115 s conforme o
modelo) nem estado de conversa, e não dá controle sobre marcação e foco, sem o qual não há
navegação por teclado nem verificação de contraste. O ganho decisivo em trocá-lo, porém, foi
outro: com o cliente em outro processo e outra linguagem, "a interface não importa módulo
algum do domínio" deixa de ser disciplina e passa a ser imposto pelo ambiente de execução.

---

## ADR-003 — Similaridade k-NN como mecanismo primário, sem classificador de defeito

**Contexto.** O enunciado pede que o sistema localize ocorrências passadas semelhantes ao
evento em análise e informe quantidade, distribuição temporal e frequência, ressaltando que
a solução "não depende necessariamente da classificação prévia de falhas conhecidas". Dois
fatos delimitam a decisão: o rótulo `fault` **já vem no JSON de entrada** — o exemplo do
próprio enunciado traz `"fault":"cocked_rotor_2"` —, e um classificador sobre os atributos
não generaliza.

**Decisão.** k-NN sobre atributos padronizados como único mecanismo de modelagem no caminho
crítico. O tipo de defeito vem do rótulo do operador, normalizado deterministicamente
(ADR-005). O classificador supervisionado fica apenas como experimento documentado em
[`notebooks/01-classificador-e-vazamento.ipynb`](../notebooks/01-classificador-e-vazamento.ipynb),
fora do fluxo de produção.

**Justificativa.** Um RandomForest sobre 151.064 eventos de defeito atinge **89,8%** sob
validação estratificada aleatória e **12,4%** sob GroupKFold por sessão de coleta, contra
**11,7%** de chutar sempre a classe majoritária. A diferença é vazamento: o histórico tem
159 trechos contíguos de mesmo rótulo — cada um é uma montagem de bancada, com milhares de
leituras quase idênticas gravadas em sequência —, e o sorteio aleatório os espalha entre
treino e teste. A prova é direta: um modelo treinado **só com o timestamp**, sem grandeza
física alguma, atinge 99,94% sob validação aleatória e 6,5% sob GroupKFold.

O caso é estrutural, não de ajuste. Entre as quatro famílias de rolamento o acerto na
própria classe fica **abaixo do acaso** — 0,04 a 0,18, quando chutar entre quatro daria
0,25. Separá-las exige análise espectral de envelope nas frequências características, e o
conjunto traz apenas escalares agregados por leitura, dos quais essa informação não
sobrevive. A contraprova está no mesmo experimento: `falta_fase` é a menor classe (800
eventos) e a mais bem classificada, com F1 de **0,72**, porque falha elétrica tem assinatura
que resiste à agregação escalar. Onde há sinal o modelo o encontra; onde não há, ele não
inventa.

Colocar um componente no nível do baseline entre a entrada e a prescrição seria construir a
peça mais frágil do sistema sem necessidade, já que o rótulo é fornecido. O k-NN permanece
porque responde ao que foi pedido e é explicável por construção: a resposta *é* a lista de
vizinhos, cada um rastreável até seu `id` e sua data. Em troca, o sistema depende de a
anotação do operador estar correta — um rótulo errado roteia para o documento errado —, e
inferi-lo com 12% de acerto seria estritamente pior.

---

## ADR-004 — Guardrail contra alucinação: sem documento, sem recomendação

**Contexto.** O enunciado determina que o sistema se detenha unicamente a problemas que
possuem documentos e, caso contrário, reporte a ausência e sugira o cadastro. "Alucinação do
modelo" é critério explícito de avaliação.

**Decisão.** Barreira determinística em código, anterior à chamada do LLM: sem trecho acima
do limiar de relevância para o defeito identificado, o modelo não é acionado e a resposta é
o texto de recusa com o convite ao cadastro. Havendo trechos, a resposta vem
obrigatoriamente com as fontes citadas.

**Justificativa.** Instrução em prompt é preferência estatística, não garantia — um modelo
de 8B a viola sob pressão de contexto, e verificar a resposta depois exigiria um segundo
modelo tão falível quanto o primeiro. Retirar do modelo a possibilidade de responder é o que
torna o comportamento verificável: o teste afirma que o cliente do LLM recebe zero chamadas
nos caminhos de recusa.

O sistema passa a recusar casos que talvez pudesse responder. É a troca certa — em
manutenção industrial o custo de uma prescrição inventada é intervenção errada em
equipamento crítico, e "não sei, documente" é resposta segura.

---

## ADR-005 — Normalização canônica dos rótulos de falha

**Contexto.** A coluna `fault` traz **151 rótulos distintos** para **17 entidades reais** —
12 famílias de defeito e 5 estados —, fragmentadas por sufixos de sessão de coleta (`_2`,
`_pos_2`, `_carga`, `_adxl_0`), prefixos de lote (`new_*`, `_novo`) e erros de digitação do
operador, já que a anotação é manual: `desbalanceamento`, `cockecocked_adxl_0`,
`normla_carga_3_3`, `mortor_desligado_novo`.

**Decisão.** Camada de normalização determinística por regras explícitas, mapeando os 151
rótulos brutos para 17 formas canônicas antes de qualquer roteamento ou busca. As regras
ficam em módulo versionado e coberto por testes, e os erros de digitação são aliases
declarados — não correção automática.

**Justificativa.** Sem esta camada o guardrail do ADR-004 dispara errado: **421 eventos**
grafados com erro seriam tratados como defeito desconhecido e teriam atendimento recusado,
embora estejam integralmente cobertos pelo Doc3. Um guardrail que recusa o que sabe responder
destrói a confiança do usuário sem oferecer proteção alguma.

Correção automática por distância de edição foi descartada: introduziria um segundo
componente probabilístico onde um dicionário resolve com certeza, e `desalinhado` e
`desbalanceado` estão a poucas edições um do outro — um erro que seria grave e silencioso. Um
rótulo verdadeiramente novo, ainda não mapeado, cai no caminho de "defeito sem documentação"
(ADR-006), que é o comportamento desejado.

---

## ADR-006 — Três caminhos de resposta, não dois

**Contexto.** Dos 166.796 eventos, **15.732 (9,4%) são estados do sistema, não defeitos**:
`normal` (15.058), `motor_desligado` (497), `teste` (101), `baseline` (69) e `acelerando`
(7). O enunciado determina explicitamente que esses rótulos não representam problemas.

**Decisão.** Três caminhos mutuamente exclusivos, decididos deterministicamente após a
normalização (ADR-005): **estado do sistema**, que recebe o contexto estatístico sem
prescrição; **defeito com documentação**, que recebe prescrição com fontes citadas; e
**defeito sem documentação**, que recebe recusa e convite ao cadastro (ADR-004).

**Justificativa.** Com apenas dois caminhos, um evento `normal` produziria "não existe
documento para o defeito `normal`" — factualmente correta e errada em substância. Ela afirma
que `normal` é um defeito, contradiz o enunciado e, ao vivo, é indistinguível de um defeito
de implementação. Prescrever manutenção para máquina desligada é erro tão grave quanto
inventar procedimento.

A verificação de estado ocorre sobre a forma canônica, nunca sobre o rótulo bruto:
`baseline` não aparece literalmente no conjunto — existe só como `new_baseline`, 69 eventos
—, e uma regra por igualdade exata contra a lista do enunciado os deixaria passar como
defeito.

---

## ADR-007 — Seleção de atributos: 16 das 23 colunas numéricas

**Contexto.** O CSV traz 23 colunas numéricas, várias delas transformações exatas de outras.
Duas camadas de redundância foram confirmadas: conversão de unidade (`*_in_s` ↔ `*_mm_s`,
`temperature_f` ↔ `temperature_c`, todas com r > 0,999999) e derivação interna do firmware —
`peak_velocity = rms_velocity × √2` exatamente, r = 1,000000 em ambos os eixos, porque o
sensor assume onda senoidal pura. As oito colunas de velocidade contêm dois graus de
liberdade.

**Decisão.** Conjunto mínimo de **16 atributos** (15 métricas mais `rpm`), removendo as sete
colunas redundantes: as quatro `*_velocity_in_s`, as duas `*_peak_velocity_mm_s` e
`temperature_f`. `created_at` jamais entra como atributo.

**Justificativa.** A distância euclidiana do k-NN é sensível a essa redundância: com as 23
colunas, o eixo de velocidade entra na conta **três vezes** e recebe peso triplo sobre
temperatura, kurtosis ou crest factor. A busca passaria a ser dominada por uma grandeza
única, por acidente de formatação do CSV. PCA foi descartado porque destruiria a
interpretabilidade dos vizinhos, que é o que torna a resposta defensável perante um técnico.

`created_at` fica fora pelo motivo do ADR-003 — prediz `fault` quase perfeitamente, e seu
lugar é na saída, alimentando a distribuição temporal. Três observações ficam registradas para
o pré-processamento: `z_kurtosis` satura em 65.535 (estouro de registrador uint16, não valor
físico); `temperature_c` codifica sobretudo a deriva térmica da bancada ao longo dos 47 dias,
sendo proxy temporal e não discriminante físico; e 9.739 linhas (5,84%) têm vetor idêntico ao
de outra, o que infla a contagem de eventos similares e exige deduplicação no índice.

---

## ADR-008 — Escopo da busca por similaridade: global, com o defeito de cada vizinho exibido

**Contexto.** Definido o k-NN como mecanismo primário (ADR-003), resta decidir se a busca
percorre todo o histórico ou apenas os eventos que compartilham o rótulo do evento de
entrada.

**Decisão.** Busca global, exibindo a que família de defeito pertence cada vizinho.

**Justificativa.** Restringir a busca ao próprio rótulo torna o resultado circular: filtra-se
pelo defeito anotado para em seguida informar que os eventos semelhantes têm esse defeito. A
busca global é fiel à formulação do enunciado — "não depende necessariamente da classificação
prévia de falhas conhecidas" — e informa: os vizinhos mais próximos de um evento de
`rolamento_inner` pertencem majoritariamente a `rolamento_outer` e `rolamento_combination`,
que é a evidência visual do que o ADR-003 sustenta com números. O contexto fica mais ruidoso
do que seria com recorte por defeito, e o ruído *é* o achado.

---

## ADR-009 — Pipeline de recuperação documental

**Contexto.** Seis PDFs, 62 páginas em português, todos com a mesma estrutura de seções
numeradas. Cinco têm texto nativo extraível; o Doc1 é digitalizado e exige OCR (ADR-012). O
índice resultante é pequeno, de modo que a decisão é limitada por precisão de recuperação e
qualidade de citação, não por desempenho.

**Decisão.** Fatiamento por seção numerada; `multilingual-e5-large` como modelo de
embeddings; ChromaDB para os vetores e SQLite para os dados relacionais.

**Justificativa.** O fatiamento por seção acompanha a estrutura que os próprios autores
impuseram ao conteúdo: cada seção é uma unidade semântica completa, e um procedimento passo a
passo é recuperado inteiro, nunca truncado no meio de uma sequência que o técnico precisa
seguir. Como subproduto a citação fica precisa e verificável — "Doc1, seção 19" —, o que
sustenta a rastreabilidade exigida pelo ADR-004; janela fixa produziria citação vaga e
cortaria procedimentos ao meio.

O `multilingual-e5-large` foi treinado como multilíngue, e não adaptado do inglês, o que
importa porque documentos e perguntas são em português; com 1,1 GB cabe na GPU ao lado do LLM
(ADR-001). ChromaDB é embutido e persiste em disco sem serviço externo, coerente com operação
em estação única. PostgreSQL com pgvector seria a escolha definitiva em arquitetura
industrial e está registrado em `docs/arquitetura.md` como caminho de evolução — foi preterido
pelo custo de configuração dentro das 72 horas.

Sem busca léxica, termos técnicos exatos (`BPFO`, "pé manco") dependem inteiramente da
representação vetorial. O risco é contido pelo filtro por documento do ADR-010, que reduz o
espaço de busca antes da consulta semântica; a busca híbrida com BM25 fica como melhoria
natural.

---

## ADR-010 — Guardrail em duas barreiras: roteamento determinístico e limiar calibrado

**Contexto.** O ADR-004 estabelece que o sistema não responde sem respaldo documental. Resta
definir *como* essa ausência é constatada.

**Decisão.** Duas barreiras em sequência. A primeira é determinística: o defeito canônico
(ADR-005) é consultado no mapa defeito → documento, artefato versionado e explícito; sem
documento mapeado, o LLM não é acionado. A segunda é semântica: havendo documento, a
recuperação ainda precisa devolver trecho acima do limiar de **0,8400**, calibrado sobre 44
perguntas de resposta conhecida. A consulta enviada ao índice é `"{condição}: {pergunta}"`.

**Justificativa.** A primeira barreira é impossível de furar porque não envolve modelo algum
— é consulta a dicionário, e é ela que garante o comportamento exigido pelo enunciado. A
segunda cobre o caso em que existe documento para o defeito, mas nenhuma seção responde à
pergunta específica do técnico. Calibrar em vez de arbitrar transforma um número mágico em
número defensável.

O conjunto de calibração precisou ser refeito. O primeiro tinha 30 perguntas longas e bem
formuladas, produzia separação perfeita e um corte em 0,8569 — que recusava *"o eixo pode
estar empenado?"* (0,8395) sobre um evento de `cocked_rotor`, cujo documento tem uma seção
inteira sobre inspeção do eixo. **O comprimento do texto domina a similaridade de cosseno:**
comparar três palavras com uma seção inteira mede diferença de tamanho, não pertinência.
Ninguém digita "qual o procedimento para substituir um rolamento danificado" num chat, digita
"e o rolamento?". Ancorar a consulta na condição devolve a massa semântica que a conversa
deixa implícita.

Com o conjunto realista — 44 perguntas, metade curtas — as distribuições se sobrepõem e
nenhum corte acerta os dois lados: 0,8400 aceita 24/24 legítimas barrando 10/20
impertinentes; 0,8590 barraria 19/20 ao custo de recusar 5 legítimas. O limiar opera como
**piso** porque uma recusa indevida custa mais que uma passagem indevida: a recusa é visível,
frustra o técnico diante de pergunta pertinente e ensina a não confiar no sistema, enquanto a
passagem indevida entrega uma resposta que, no pior caso, informa que o procedimento não
trata do assunto. O caso central — defeito sem procedimento algum — já foi resolvido pela
primeira barreira.

A segunda barreira barra, portanto, metade das perguntas fora de escopo, não a totalidade. A
busca híbrida com BM25 registrada no ADR-009 atacaria exatamente esta limitação: termos
técnicos exatos dariam ao sinal léxico a discriminação que o comprimento do texto rouba do
sinal semântico.

---

## ADR-011 — `eccentric_rotor` classificado como defeito sem documentação

**Contexto.** `eccentric_rotor` responde por 16.497 eventos (10,9% do conjunto) e não tem
documento dedicado. Existe documentação *adjacente*: a seção 8 do Doc5 trata de
excentricidade, mas de **polia**, e prescreve reinstalar ou substituir a polia.

**Decisão.** Tratar como defeito sem documentação, seguindo o caminho de recusa do ADR-004.

**Justificativa.** Rotor excêntrico e polia excêntrica são defeitos distintos, em componentes
distintos, com correções distintas — o próprio Doc6 trata o rotor como assunto separado.
Prescrever "reinstale a polia" diante de um rotor excêntrico é precisamente a alucinação
*plausível*: superficialmente pertinente, tecnicamente errada, e capaz de levar um técnico a
intervir no componente errado de um equipamento crítico. Um mapeamento automático por
similaridade de nomes ligaria os dois.

Responder com ressalva foi descartado por criar um quarto caminho, "responder com dúvida",
difícil de definir e de defender como regra. A cobertura cai para 80,4% dos eventos de
defeito, e é o custo de não errar: a resposta correta em operação é a que o sistema já dá —
cadastre o procedimento de rotor excêntrico. É esta decisão que mostra que o guardrail não é
verificação contra lista de rótulos conhecidos, e sim julgamento sobre o que constitui
respaldo documental suficiente.

---

## ADR-012 — OCR para o Doc1, digitalizado

**Contexto.** O Doc1 não tem camada de texto: 17 páginas, **zero caracteres extraíveis**, 18
imagens. É documento digitalizado, e a inspeção inicial não percebeu porque foi feita numa
ferramenta que renderiza a página visualmente. Ele não é dispensável — é o único procedimento
que cobre as quatro famílias de falha de rolamento, **60.779 eventos, 40,2% de todos os
defeitos**. Sem ele a cobertura cai de 80,4% para 40,2%, e o guardrail passa a recusar a
família de defeito mais frequente.

**Decisão.** OCR com RapidOCR (`rapidocr-onnxruntime`) sobre páginas rasterizadas por
`pypdfium2`, aplicado só aos documentos sem camada de texto. A extração escolhe a estratégia
por documento e guarda o resultado em cache.

**Justificativa.** Descartar o Doc1 seria abrir mão de 40% da cobertura por limitação de
ferramenta, não por ausência de informação. Entre as rotas de OCR, RapidOCR instala-se
inteiramente por `pip` e roda sobre ONNX Runtime em CPU, sem binário de sistema nem pacote de
idioma à parte: mantém o repositório reproduzível por quem só executa `pip install -r
requirements.txt` e preserva a operação offline que sustenta o ADR-001. Tesseract entrega
qualidade equivalente ou superior, ao custo de uma dependência fora do ecossistema Python.

O OCR introduz ruído de reconhecimento que não existe nos outros cinco documentos. Duas
medidas contêm o efeito: o texto é normalizado antes do fatiamento, e a qualidade da extração
é verificada por teste contra marcadores conhecidos do documento. A situação, aliás, é a
realidade de qualquer base documental industrial — procedimentos antigos existem como
digitalizações de papel —, e o enunciado lista "tratamento dos documentos fornecidos" como
item próprio do desafio.

---

## ADR-013 — Modelo de linguagem selecionável por ambiente

**Contexto.** O ADR-001 dimensionou o 7B quantizado para a estação do enunciado, com GPU de
16 GB. A máquina de desenvolvimento e demonstração tem gráficos integrados, e o Ollama
executa em CPU: o 7B leva **115 s** por geração e o 3B, **32 s**. Na GPU prevista para
operação o 7B responderia em poucos segundos — a lentidão é do hardware, não da arquitetura.

**Decisão.** O modelo é lido da variável de ambiente `MODELO_LLM`, com o Qwen2.5 7B como
padrão e o 3B documentado para hardware sem GPU dedicada. A geração incremental é oferecida
à interface de chat independentemente do modelo.

**Justificativa.** Reduzir o contexto do 7B para ganhar tempo foi descartado de imediato:
encurtar os trechos recuperados degrada exatamente o que a solução entrega. É otimizar a
métrica errada.

A troca de modelo é possível por causa do desenho do RAG. Como toda a competência técnica da
resposta vem dos trechos recuperados, e não do que o modelo memorizou, trocar 7B por 3B custa
fluência de redação, não conteúdo — as citações continuam corretas porque são determinadas
pela recuperação. Um sistema que dependesse do conhecimento interno do modelo não toleraria a
troca, e o fato de tolerar é evidência de que o desenho está certo. Ler o modelo do ambiente
é também o que permite dimensionar a instalação por planta sem alterar código.

---

## ADR-014 — Cobertura documental em duas camadas, com cadastro e remoção em operação

**Contexto.** O ADR-010 estabeleceu o mapa defeito → documento como primeira barreira, e o
enunciado exige que o sistema, ao recusar, sugira registrar um novo documento. Um mapa
estático em código torna essa sugestão vazia: o técnico cadastraria o procedimento e o sistema
continuaria recusando, porque a cobertura só mudaria com alteração de código-fonte.

**Decisão.** Duas camadas. O mapa em `src/rag/mapeamento.py` permanece estático, versionado e
coberto por testes — descreve a base entregue. Um registro em SQLite guarda as associações
criadas em operação e **preenche as lacunas** do mapa, que é consultado primeiro. `POST
/documentos` cadastra e `DELETE /documentos/{condicao}` desfaz, ambos válidos na consulta
seguinte, sem reiniciar o serviço. A remoção apaga índice, registro e o PDF em disco.

**Justificativa.** As duas camadas respondem a perguntas diferentes. O mapa é afirmação de
projeto, e sua estabilidade é o que permite testá-lo e defendê-lo — é dele que sai a recusa de
`eccentric_rotor` do ADR-011. O registro é estado operacional, criado pela equipe em resposta
às próprias recusas do sistema, e muda sem passar por revisão de código.

Migrar tudo para o banco apagaria essa distinção e, com ela, a possibilidade de verificar por
teste que `falta_fase` não tem documento. Manter tudo em código transformaria o convite ao
cadastro em promessa não cumprida — o defeito mais grave num sistema cuja tese é não prometer
o que não pode entregar.

O mapa vence o registro, e não o contrário: um procedimento revisto e versionado não deve ser
substituído por um PDF enviado em operação. Pelo mesmo motivo a remoção alcança só a camada de
cima — uma rota HTTP não apaga uma linha de código —, e uma condição coberta pelo mapa recebe
404 com o motivo dizendo qual documento a atende.

Recadastrar substitui em vez de acumular, tanto no registro quanto no índice: o `upsert` do
Chroma atualiza os ids recebidos e não apaga os ausentes, de modo que um procedimento com
menos seções que o anterior deixaria as excedentes recuperáveis e citáveis como fonte de
documento revogado. O PDF sai do disco junto na remoção — mantê-lo daria rastreabilidade pela
metade, já que nada o referencia e o próximo cadastro para a mesma condição o sobrescreveria.

---

## ADR-015 — Design system com verificação automática, em vez de convenção

**Contexto.** Depois de construída a interface, um levantamento encontrou **vinte e duas
medidas de texto distintas**, todas escritas como valor arbitrário no ponto de uso
(`text-[0.79rem]`). O mesmo valia para raios, tamanhos de ícone e os eixos dos gráficos.
Nenhum desses valores era decisão: eram ajustes locais, cada um razoável no momento e nenhum
defensável depois. Uma escala de sete degraus chegou a ser declarada em `index.css`, mas
nenhum componente a consumia.

**Decisão.** `web/src/index.css` é a única fonte de verdade da aparência — cor, tipografia,
raio, dimensão, sombra e tempo de transição —, e dois verificadores rodam dentro de `npm run
build`: `verificar-tokens.mjs` reprova medida absoluta, cor literal, opacidade fora dos
degraus e token declarado que ninguém consome; `verificar-contraste.mjs` mede os pares de cor
contra o mínimo da WCAG 2.1 AA, lendo os valores do próprio CSS.

**Justificativa.** Manter a escala como convenção documentada é exatamente o que já havia
sido tentado, e o resultado está medido acima: ela existia e foi ignorada. Um design system
que depende de disciplina se dissolve na primeira pressa. Uma biblioteca de componentes
pronta traria dezenas de variantes não usadas e substituiria decisões explicáveis por padrões
de terceiros — não se defende o que não se escolheu. A verificação automática muda a natureza
da regra: deixa de ser recomendação e passa a ser condição de build.

Dois pontos exigiram tratamento próprio. Os gráficos recebem tamanho e altura como números em
JavaScript, onde `fontSize: 11` escaparia a qualquer verificador textual — por isso
`src/estilo.ts` **lê os tokens do documento** em tempo de execução, em vez de repeti-los. E o
verificador de contraste existe porque o CSS afirmava que as cores tinham sido medidas: a
medição cobria a separação entre marcas de gráfico sob daltonismo, nunca o contraste de
texto, e quatro pares reprovavam em silêncio.

O verificador é textual e não entende o código — um valor escondido atrás de concatenação de
string passaria. Aceita-se, porque o alvo não é o adversário determinado, e sim o próprio
autor com pressa.

---

## ADR-016 — Modelo fora do ar é 503, não 500

**Contexto.** Com o Ollama parado, o caminho de prescrição devolvia **HTTP 500** e a interface
exibia *"A API não está respondendo — suba a API"*. As duas afirmações eram falsas: a API
respondeu, e o processo a reiniciar era outro. Numa demonstração ao vivo, isso manda o
apresentador digitar o comando errado enquanto o problema real continua de pé — e o sistema
já sabia, porque `GET /sistema` publicava `modelo_disponivel`.

**Decisão.** Uma exceção de domínio, `ModeloIndisponivel`, traduzida por um
`exception_handler` em **503 com `Retry-After: 10`**, com a mensagem distinguindo serviço
parado (`ollama serve`) de modelo não baixado (`ollama pull`).

**Justificativa.** A API é o contrato de integração (ADR-002), e o código de status é a parte
que um supervisório lê primeiro. `500` significa defeito não tratado — vira chamado de
suporte; `503` significa dependência indisponível e é retentável por convenção. Devolver 500
para condição prevista e recuperável mente sobre a natureza da falha. Corrigir apenas o texto
da interface não resolveria: um segundo cliente da API continuaria recebendo a informação
errada. Verificar a disponibilidade na entrada de cada rota também não, porque tornaria as
**recusas** dependentes de o modelo estar no ar — o acoplamento que o ADR-004 existe para
impedir.

Uma sutileza ficou registrada no código: `responder_em_fluxo` deixou de ser função geradora.
Sendo geradora, nada dentro dela executava até o primeiro `next()`, que acontece **depois** de
os cabeçalhos terem sido enviados — quando devolver 503 já é impossível.

A consequência virou argumento: com o modelo derrubado, **três dos quatro caminhos seguem
respondendo 200** — as duas recusas e o estado operacional. Não é tolerância acidental, é o
ADR-004 se verificando sob estresse, já que os textos de recusa são compostos em código e
nunca gerados. `tests/test_api_modelo_fora.py` afirma isso: se um dia essas rotas passarem a
depender do LLM, o teste falha.

---

## ADR-017 — As campanhas de ensaio, medidas corretamente

**Contexto.** O painel exibia, sob a série temporal, que cada campanha de ensaio concentra um
modo de falha "em janelas quase disjuntas". Medida pelo primeiro e último evento de cada
condição, a afirmação **é falsa**: `desbalanceado` é ensaiado no fim de abril e reaparece em
junho, de modo que sua janela cobre os 47 dias inteiros. Desenhar as faixas com esse dado
teria produzido doze retângulos empilhados cobrindo o gráfico — a refutação visual da legenda
logo abaixo.

**Decisão.** A estatística passa a ser a **condição que domina cada dia**, agrupada em
`campanhas: list[BlocoDeCampanha]` — trechos contíguos de dias com a mesma dominante, cada um
carregando a dominância média. A legenda afirma o que foi medido: de 30/04 a 28/05, dez blocos
com 61% a 100% dos eventos do dia numa só condição; de 01/06 em diante, campanhas sobrepostas
com 22% a 63%. Mediana de 74%, em 18 blocos contíguos.

**Justificativa.** O argumento do ADR-003 não precisava do exagero e fica mais forte sem ele:
basta que a data carregue informação sobre o rótulo — o que os dois regimes sustentam — para
explicar por que a validação por amostragem aleatória infla a acurácia. Afirmar "janelas
disjuntas" diante de uma banca que pode abrir o CSV era apostar em ninguém conferir.

O erro sobreviveu porque a frase foi escrita a partir de uma impressão da análise exploratória
e nunca reconferida contra uma estatística. A regra que fica: **afirmação numérica exibida na
interface precisa vir de um campo calculado**, não de texto redigido — e por isso o intervalo,
os percentuais e o número de blocos saem todos da API. O campo antigo, além de enganoso, era
código morto: estava declarado e nenhum consumidor o lia.