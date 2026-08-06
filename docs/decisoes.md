# Registro de Decisões Técnicas

Formato de cada registro: **contexto → alternativas consideradas → decisão → justificativa
→ consequências aceitas**. O objetivo é que qualquer decisão da solução possa ser defendida
sem recorrer à memória.

---

## ADR-001 — LLM local via Ollama

**Contexto.** A solução precisa gerar recomendações em linguagem natural a partir da
documentação técnica. O enunciado permite treinar em infraestrutura de alto desempenho, mas
exige que a operação rode em estação comercial com até 32 GB de RAM e GPU de 16 GB.

**Alternativas.** (a) API externa de LLM; (b) modelo local quantizado servido por Ollama;
(c) camada de abstração com os dois.

**Decisão.** Modelo local de 7–8B parâmetros quantizado, servido por Ollama.

**Justificativa.** Um modelo dessa faixa quantizado ocupa aproximadamente 5–6 GB de VRAM,
cabendo com folga no limite de 16 GB junto com o modelo de embeddings. Mais importante:
chão de fábrica frequentemente opera em rede segregada, e dados de processo industrial são
sensíveis do ponto de vista concorrencial — uma solução que depende de API externa cria
dependência de conectividade e expõe dado operacional a terceiros.

**Consequências aceitas.** Qualidade de geração inferior à de modelos de fronteira. Mitigada
pelo desenho do RAG: o modelo não precisa *saber* nada sobre manutenção, apenas redigir a
partir dos trechos recuperados.

---

## ADR-002 — FastAPI para a camada de serviço e Streamlit para a interface

> **Superado em parte pelo [ADR-002-A](#adr-002-a--interface-própria-em-react-no-lugar-do-streamlit).**
> A decisão de expor a solução como API REST — que é o cerne deste registro — **permanece**
> e é a fronteira que sustenta toda a arquitetura. O que mudou foi o cliente: a interface
> é React, não Streamlit. O registro fica como estava, porque a escolha original era
> razoável e foi o uso que a derrubou.

**Contexto.** A entrega precisa de chat, dashboard e upload de documentos, e a integração em
ambiente industrial é critério de diferencial.

**Alternativas.** (a) aplicação Streamlit monolítica; (b) FastAPI + Streamlit; (c) FastAPI +
front-end próprio.

**Decisão.** FastAPI expondo a solução como API REST documentada, com Streamlit atuando como
cliente.

**Justificativa.** Em ambiente industrial, o consumidor natural do sistema não é uma pessoa
em um navegador: é o supervisório, o CMMS ou o broker de mensagens que recebe os eventos dos
sensores. Uma API é o contrato que torna essa integração possível; a interface é apenas um
dos clientes. A separação também permite evoluir ou substituir a camada visual sem tocar na
lógica.

**Consequências aceitas.** Dois processos para orquestrar em vez de um — resolvido com Docker
Compose.

---

## ADR-002-A — Interface própria em React, no lugar do Streamlit

> Complementa o ADR-002. A decisão de expor a solução como **API REST** permanece
> intacta — é a alternativa (c) daquele registro, que na época foi descartada por custo,
> passando a ser a escolhida. O que segue é o motivo.

**Contexto.** O ADR-002 escolheu Streamlit como cliente da API por ser o caminho mais
curto até um dashboard funcional. Ao implementar, três exigências apareceram e nenhuma
delas cabia bem no modelo de execução do Streamlit, que **reexecuta o script inteiro a
cada interação** e mantém o estado num dicionário de sessão:

1. **Resposta transmitida em partes.** Em CPU a geração leva de 32 s a 115 s conforme o
   modelo (ADR-013). Sem ver o texto surgindo, a espera lê como travamento. O
   `POST /chat/fluxo` existe para isso, e consumir um fluxo HTTP dentro de um script que
   se reinicia a cada evento é trabalhar contra a ferramenta.
2. **Conversa com histórico.** O chat precisa de turnos anteriores para que "e se o eixo
   estiver empenado?" faça sentido. Estado conversacional sobre reexecução total é
   possível, mas cada widget novo acrescenta uma chance de perder o fio.
3. **Acessibilidade e identidade visual.** O Streamlit não expõe controle sobre marcação
   e foco, o que inviabiliza navegação por teclado, `role` correto e a verificação de
   contraste que o ADR-015 tornou executável.

**Alternativas.** (a) permanecer no Streamlit e aceitar as três limitações; (b) Streamlit
com componentes customizados em JavaScript — que é escrever front-end mesmo, só que
dentro de uma camada a mais; (c) interface própria em React consumindo a mesma API.

**Decisão.** (c). React 19 + Vite + TypeScript + Tailwind v4, em `web/`, consumindo
exclusivamente os sete endpoints HTTP.

**Justificativa.** A tese do ADR-002 é que *a API é o contrato e a interface é apenas um
cliente*. Com Streamlit, essa fronteira é uma promessa: nada impede um `import` de
`src.rag.roteador` numa tela, e o dia em que alguém o fizer, a separação some sem que
nenhum teste reclame. Com um cliente em **outro processo e outra linguagem**, a fronteira
deixa de depender de disciplina — ela é imposta pelo ambiente de execução. A afirmação
"a interface não importa módulo algum do domínio" passou de convenção a fato verificável.

O custo real foi menor que o estimado no ADR-002 porque a API já existia, completa e
documentada, antes da primeira linha de interface. Foi a ordem de construção — API antes
de tela — que tornou a troca barata, e é ela o argumento a defender, não a escolha de
biblioteca.

**Consequências aceitas.** Uma cadeia de build a mais (Node) e um processo a mais em
operação. Ambos resolvidos pelo `docker-compose.yml`, que constrói o estático e o entrega
por nginx — o mesmo contêiner que encaminha `/api` ao serviço Python, reproduzindo em
produção o proxy que o `vite.config.ts` monta em desenvolvimento. Isso corrige, e desta
vez implementa, a consequência que o ADR-002 dava por resolvida.

O broker MQTT descrito em `arquitetura.md` §8 **não** entrou na orquestração: não existe
adaptador que fale com ele, e subir um broker inerte seria encenar uma integração que não
foi feita.

**O empacotamento pagou por si.** Construir a imagem e subir a pilha expôs dois defeitos
que a máquina de desenvolvimento escondia, ambos fatais para quem clonasse o repositório:

- `requirements.txt` declarava `httpx==0.28.1`, incompatível com o cliente do Ollama
  (`httpx<0.28.0`). O ambiente local usava 0.27.2 desde sempre — o arquivo é que estava
  errado. Num ambiente limpo, `pip install -r requirements.txt` **falhava na primeira
  linha de instalação**, e nenhum teste podia detectar isso, porque testes rodam sobre um
  ambiente já montado.
- As fábricas de `src/api/dependencias.py` memoizavam com `lru_cache`, que **não é
  atômico**. Requisições concorrentes durante a subida — o comportamento normal de um
  cliente que repete a chamada porque a primeira ainda não voltou — entravam todas na
  construção e alocavam cada uma sua cópia do modelo de 1,1 GB. Sob o limite de memória
  do contêiner, o processo era encerrado e reiniciado em laço. Com 15,7 GB de RAM na
  máquina de desenvolvimento, o mesmo defeito só desperdiçava memória em silêncio.

**Consequência de método:** *empacotar é um teste*. Ele exercita a hipótese que a suíte
não alcança — a de que o projeto se monta do zero — e é a única verificação que reproduz
o que a banca vai fazer.

---

## ADR-003 — Busca por similaridade (k-NN) como mecanismo primário; sem classificador de defeito no caminho crítico

> **Revisão 1** — após a análise exploratória. A versão inicial previa um classificador
> supervisionado em paralelo ao k-NN; a evidência empírica levou ao descarte dessa peça. O
> histórico fica registrado de propósito: a decisão anterior era razoável *a priori*, e foi a
> medição que a derrubou.
>
> **Revisão 2 (05/08/2026)** — os números foram **reexecutados** e agora vivem em
> `notebooks/01-classificador-e-vazamento.ipynb`. Três mudanças em relação ao que estava
> escrito aqui:
>
> - os valores diferem um pouco dos registrados na primeira medição (89,8% e 12,4%, contra
>   87,2% e 11,1%), porque aquela não deixou script e a definição de sessão não estava
>   explicitada. Os atuais são reproduzíveis célula a célula;
> - *"cai abaixo do baseline"* virou *"fica no nível do baseline"*, que é o que a medição
>   sustenta com a definição de sessão mais natural;
> - a afirmação de que fixar o rpm não alteraria o quadro (10,4%) foi **removida**: não foi
>   reproduzida, e número não verificado não fica em documento de defesa.

**Contexto.** O enunciado pede que o sistema localize ocorrências passadas com
características próximas às do evento em análise e informe quantidade, distribuição temporal
e frequência, ressaltando que a solução "não depende necessariamente da classificação prévia
de falhas conhecidas". Dois fatos observados nos dados delimitam a decisão:

1. **O rótulo `fault` já vem no JSON de entrada.** O exemplo do próprio enunciado traz
   `"fault":"cocked_rotor_2"`. A condição é anotada manualmente pelo operador — o sistema a
   recebe, não precisa inferi-la.
2. **Um classificador de defeito a partir das features não generaliza.** Medição em
   `banner.csv` (151.064 eventos de defeito, 12 famílias), reproduzível em
   [`notebooks/01-classificador-e-vazamento.ipynb`](../notebooks/01-classificador-e-vazamento.ipynb):

   | Protocolo de validação | RandomForest | k-NN (k=5) |
   | --- | --- | --- |
   | CV estratificada aleatória | 89,8% | 65,4% |
   | **GroupKFold por sessão de coleta** | **12,4%** | **10,3%** |
   | *Baseline — prever sempre a classe majoritária* | *11,7%* | *11,7%* |

   **A prova do vazamento é direta, não é inferência.** Um RandomForest treinado apenas com
   o *timestamp* — nenhuma grandeza de vibração, só o relógio — atinge **99,94%** sob
   validação aleatória, e cai a 6,5% sob GroupKFold. Um modelo sem informação física alguma
   explica praticamente todo o resultado do modelo completo: o que a validação aleatória
   mede é a capacidade de memorizar o calendário da bancada.

   **O número honesto é uma faixa, não um valor**, porque depende de como se define sessão:

   | Definição de sessão | Grupos | Acurácia |
   | --- | --- | --- |
   | Rótulo bruto | 120 | 10,9% |
   | Trecho contíguo de mesmo rótulo | 159 | 12,4% |
   | Dia de coleta | 29 | 25,0% |

   Nenhuma leitura torna o classificador útil, mas registrar a faixa importa: quem refizer o
   experimento com outra definição encontrará outro número, e é melhor que a variação já
   esteja documentada.

**Alternativas.** (a) apenas k-NN; (b) apenas classificação supervisionada; (c) detecção de
anomalia por autoencoder; (d) k-NN e classificador em conjunto.

**Decisão.** k-NN sobre atributos padronizados como único mecanismo de modelagem no caminho
crítico. O tipo de defeito vem do rótulo do operador, normalizado deterministicamente
(ADR-005). O classificador supervisionado é mantido apenas como experimento documentado no
notebook de análise, fora do fluxo de produção.

**Justificativa.** Os 89,8% da validação aleatória são vazamento de sessão. O histórico tem
**159 trechos contíguos de mesmo rótulo** — cada um é uma montagem de bancada, com o defeito
instalado e milhares de leituras gravadas em sequência. Leituras do mesmo trecho são quase
idênticas entre si, e o sorteio aleatório as espalha entre treino e teste: o modelo é
avaliado em cópias do que acabou de estudar. Duas famílias (`correia`, `polia`) têm apenas
**duas** montagens em todo o conjunto.

Separadas as sessões, o desempenho fica **no nível do baseline da classe majoritária** — em
12,4% contra 11,7%, ou abaixo dele conforme a definição de sessão. O classificador não sabe
nada.

O caso é estrutural, não de ajuste. Entre as quatro famílias de rolamento, o acerto na
própria classe fica **abaixo do acaso**: 0,04 a 0,18, quando chutar entre as quatro daria
0,25. O modelo não apenas erra — erra sistematicamente para a família vizinha, o retrato de
um atributo que não carrega a distinção pedida. Separá-las exige análise espectral de
envelope nas frequências características (BPFI, BPFO, BSF), e o conjunto contém apenas
escalares agregados por leitura, dos quais essa informação não sobrevive.

**A contraprova está no mesmo experimento.** `falta_fase` é a menor classe do conjunto — 800
eventos contra 17.712 da maior — e é a mais bem classificada, com F1 de **0,72**. Falta de
fase é defeito elétrico, com assinatura em frequência característica que sobrevive à
agregação escalar. Onde há sinal, o modelo o encontra; onde não há, ele não inventa. Isso
separa *"o modelo está mal ajustado"* de *"os dados não contêm a resposta"*.

**Ressalva registrada.** `correia` e `polia` têm duas sessões cada, e `ventoinha`, quatro:
parte do colapso dessas três é escassez de montagens, não ausência de sinal físico. Não
salva o classificador — as famílias de rolamento têm de 15 a 19 sessões e ainda assim ficam
abaixo do acaso —, mas omitir a ressalva seria apresentar apenas o que confirma a tese, que
é o mesmo defeito de método dos 89,8%.

Colocar um componente com 11% de acurácia entre a entrada e a prescrição seria escolher
construir a peça mais frágil do sistema sem necessidade alguma, já que o rótulo é fornecido.
O k-NN permanece porque responde ao que foi de fato pedido — as ocorrências semelhantes e
suas estatísticas — e é intrinsecamente explicável: a resposta *é* a lista de vizinhos, cada
um rastreável até seu `id` e sua data.

**Consequências aceitas.** O sistema depende de a anotação do operador estar correta; um
rótulo errado na entrada produz roteamento documental errado. A alternativa — inferir o
rótulo com 11% de acerto — é estritamente pior. A validação por GroupKFold e seu resultado
ficam documentados no notebook: apresentar o número honesto e explicar sua causa física
demonstra mais domínio do que exibir os 87% obtidos com um protocolo inválido.

---

## ADR-005 — Normalização canônica dos rótulos de falha

**Contexto.** A coluna `fault` contém **151 rótulos distintos**, que não correspondem a 151
condições, mas a **17 entidades reais** — 12 famílias de defeito e 5 estados — fragmentadas
por três mecanismos: sufixos de sessão de coleta (`_2`, `_3`, `_pos_2`, `_carga`, `_adxl_0`),
prefixos de lote (`new_*`, `_novo`) e **erros de digitação do operador**, já que a anotação é
manual. Exemplos confirmados:

| Rótulo registrado | Forma correta | Eventos |
| --- | --- | --- |
| `desbalanceamento` | desbalanceado | 100 |
| `cockecocked_adxl_0` | cocked_adxl_0 | 50 |
| `ddesbalanceado_adxl_0` | desbalanceado_adxl_0 | 50 |
| `desbanlanceado_carga_3_2` | desbalanceado_carga_3_2 | 50 |
| `desabalanceado_3` | desbalanceado_3 | 50 |
| `normla_carga_3_3` | normal_carga_3_3 | 50 |
| `mortor_desligado_novo` | motor_desligado_novo | 50 |
| `dedesbalanceado_adxl_1` | desbalanceado_adxl_1 | 21 |

**Alternativas.** (a) casar o rótulo bruto diretamente contra o índice documental;
(b) normalizar por regras determinísticas para uma taxonomia canônica; (c) agrupar rótulos
por similaridade textual (distância de edição) em tempo de consulta.

**Decisão.** Camada de normalização determinística por regras explícitas, mapeando os 151
rótulos brutos para 17 formas canônicas, aplicada antes de qualquer roteamento ou busca. As
regras ficam em módulo versionado e coberto por testes, com os erros de digitação tratados
como aliases declarados — não por correção automática.

**Justificativa.** Sem esta camada, o guardrail do ADR-004 dispara **errado**: eventos
rotulados `desbalanceamento`, `ddesbalanceado_adxl_0` ou `desbanlanceado_carga_3_2` — 421 ao
todo — seriam tratados como defeitos desconhecidos e teriam atendimento recusado, embora
estejam integralmente cobertos pelo Doc3. Um guardrail que recusa aquilo que sabe responder é
pior do que a ausência de guardrail: destrói a confiança do usuário sem oferecer proteção
adicional. Correção automática por distância de edição foi descartada porque introduz um
segundo componente probabilístico onde um dicionário resolve com certeza — e porque
`desalinhado` e `desbalanceado` estão a poucas edições um do outro, um erro que seria grave e
silencioso.

**Consequências aceitas.** Um rótulo verdadeiramente novo, ainda não mapeado, cai no caminho
de "defeito sem documentação" (ADR-006) — exatamente o comportamento desejado. A tabela de
aliases exige manutenção conforme novos lotes de coleta cheguem; por isso é um artefato de
dados versionado e testado, não uma constante espalhada pelo código.

---

## ADR-006 — Três caminhos de resposta, não dois

**Contexto.** Dos 166.796 eventos, **15.732 (9,4%) são estados do sistema, não defeitos**:
`normal` (15.058), `motor_desligado` (497), `teste` (101), `baseline` (69) e `acelerando`
(7). O enunciado determina explicitamente que esses rótulos não representam problemas.

**Alternativas.** (a) dois caminhos — prescrever ou recusar por falta de documento;
(b) três caminhos, separando "não é defeito" de "é defeito sem documentação".

**Decisão.** Três caminhos mutuamente exclusivos, decididos deterministicamente após a
normalização (ADR-005):

1. **Estado do sistema** → "Nenhum defeito detectado. Equipamento em estado *X*." Segue o
   contexto estatístico do evento, sem prescrição — não há o que corrigir.
2. **Defeito com documentação** → prescrição ancorada nos trechos recuperados, com fontes
   citadas.
3. **Defeito sem documentação** → recusa explícita e convite ao cadastro de documento
   (ADR-004).

**Justificativa.** Com apenas dois caminhos, um evento `normal` produziria a resposta "não
existe documento para o defeito `normal`" — factualmente correta e completamente errada em
substância. Ela afirma que `normal` é um defeito, contradiz o enunciado e, numa demonstração
ao vivo, é indistinguível de um defeito de implementação. Cada um dos três caminhos comunica
uma situação operacional diferente e merece resposta diferente.

Detalhe de implementação que decorre desta decisão: o estado `baseline` **não aparece
literalmente** no conjunto de dados — existe apenas como `new_baseline` (69 eventos). Uma
regra de estado por igualdade exata contra a lista do enunciado deixaria esses 69 eventos
passarem como defeito. A verificação ocorre sobre a forma canônica, nunca sobre o rótulo
bruto.

**Consequências aceitas.** Uma ramificação a mais na lógica de resposta e nos testes. O custo
é baixo e a decisão é puramente determinística — nenhum dos três caminhos depende do LLM para
ser escolhido.

---

## ADR-007 — Seleção de atributos: 16 das 23 colunas numéricas

**Contexto.** O CSV traz 26 colunas: `id`, `created_at`, `fault` e **23 numéricas**. Várias
destas são transformações exatas de outras. Duas camadas de redundância foram confirmadas
empiricamente:

*Conversão de unidade* — `*_in_s` ↔ `*_mm_s` (fator 25,4) e `temperature_f` ↔
`temperature_c`, todas com r > 0,999999.

*Derivação interna do firmware* — `peak_velocity = rms_velocity × √2` exatamente
(r = 1,000000 em ambos os eixos). O firmware do sensor assume onda senoidal pura, de modo que
as colunas de velocidade de pico **não carregam informação alguma** além das de velocidade
RMS. As oito colunas de velocidade contêm, ao todo, dois graus de liberdade.

**Alternativas.** (a) usar todas as 23 colunas; (b) remover apenas as duplicatas de unidade;
(c) remover toda redundância matemática confirmada; (d) redução dimensional por PCA.

**Decisão.** Conjunto mínimo de **16 atributos** (15 métricas + `rpm`), removendo as sete
colunas redundantes: as quatro `*_velocity_in_s`, as duas `*_peak_velocity_mm_s` e
`temperature_f`.

**Justificativa.** A distância euclidiana do k-NN é diretamente sensível a essa redundância:
mantidas as 23 colunas, o eixo de velocidade entra na conta **três vezes** (RMS em duas
unidades, pico em duas unidades), recebendo peso triplo sobre temperatura, kurtosis ou crest
factor. A busca por similaridade passaria a ser dominada por uma grandeza única, por acidente
de formatação do CSV — não por decisão de engenharia. PCA foi descartado porque destruiria a
interpretabilidade dos vizinhos, justamente o que torna a resposta defensável perante um
técnico de manutenção.

**Consequências aceitas.** Três observações registradas para tratamento no pré-processamento:
`z_kurtosis` satura em 65,535 (= 2¹⁶ − 1, estouro de registrador uint16 do sensor, não valor
físico) e deve ser tratada como censurada; `temperature_c`, apesar de figurar entre os
atributos de maior importância nos testes, codifica sobretudo a deriva térmica da bancada ao
longo dos 47 dias de coleta — é proxy temporal, não discriminante físico; e 9.739 linhas
(5,84%) têm vetor de atributos exatamente idêntico ao de outra linha, o que infla a contagem
de "eventos similares" e exige deduplicação no índice ou relato separado de eventos e sessões
distintas. Pelo mesmo motivo de vazamento, `created_at` **jamais** entra como atributo:
prediz `fault` quase perfeitamente. Seu lugar é na saída, alimentando a distribuição temporal
das ocorrências semelhantes pedida pelo enunciado.

---

## ADR-008 — Escopo da busca por similaridade: global, com o defeito de cada vizinho exibido

**Contexto.** Definido o k-NN como mecanismo primário (ADR-003), resta decidir se a busca
percorre todo o histórico ou apenas os eventos que compartilham o rótulo do evento de
entrada.

**Alternativas.** (a) busca restrita ao mesmo defeito canônico; (b) busca global sobre todo
o histórico; (c) apresentar as duas visões lado a lado.

**Decisão.** Busca global, exibindo a que família de defeito pertence cada vizinho
recuperado.

**Justificativa.** Restringir a busca ao próprio rótulo torna o resultado circular: filtra-se
pelo defeito anotado para em seguida informar que os eventos semelhantes têm esse defeito. A
busca global é fiel à formulação do enunciado — "não depende necessariamente da classificação
prévia de falhas conhecidas" — e produz um resultado com valor informativo real: os vizinhos
mais próximos de um evento de `rolamento_inner` pertencem majoritariamente a
`rolamento_outer` e `rolamento_combination`, o que é a evidência visual e imediata do que o
ADR-003 sustenta com números. O usuário vê que a assinatura vibratória não separa os modos de
falha de rolamento, em vez de precisar acreditar em uma tabela de F1.

**Consequências aceitas.** O contexto estatístico apresentado é mais ruidoso do que seria com
o recorte por defeito. Isso é informação, não defeito de projeto: o ruído *é* o achado.

---

## ADR-009 — Pipeline de recuperação documental

**Contexto.** Seis PDFs, 62 páginas em português, todos com a mesma estrutura de seções
numeradas (Doc1 tem 25 seções; Doc6, 21). Cinco deles trazem texto nativo extraível; o Doc1
é digitalizado e exige OCR (ADR-012). O índice resultante é pequeno — algumas centenas de
trechos —, de modo que a decisão não é limitada por desempenho, e sim por precisão de
recuperação e qualidade de citação.

**Alternativas.** *Fatiamento:* janela fixa com sobreposição, seção numerada, ou seção com
subdivisão das mais longas. *Embeddings:* multilingual-e5-large, MiniLM multilíngue, ou
híbrido com BM25. *Armazenamento:* ChromaDB, FAISS, ou PostgreSQL com pgvector.

**Decisão.** Fatiamento por seção numerada; `multilingual-e5-large` como modelo de
embeddings; ChromaDB para os vetores e SQLite para eventos, documentos e histórico de
consultas.

**Justificativa.** O fatiamento por seção acompanha a estrutura que os próprios autores dos
procedimentos impuseram ao conteúdo: cada seção é uma unidade semântica completa, e um
procedimento de correção passo a passo — como a seção 19 do Doc1, com seus quatro casos — é
recuperado inteiro, nunca truncado no meio de uma sequência de passos que o técnico precisa
seguir. Como subproduto, a citação de fonte torna-se precisa e verificável ("Doc1, seção
19"), o que sustenta diretamente o requisito de rastreabilidade do ADR-004; uma janela fixa
produziria citações vagas e cortaria procedimentos ao meio.

O `multilingual-e5-large` foi treinado como modelo multilíngue, não adaptado do inglês, o que
importa porque tanto os documentos quanto as perguntas dos técnicos são em português. Com
cerca de 1,1 GB, cabe com folga na GPU de 16 GB ao lado do LLM (ADR-001).

ChromaDB é embutido e persiste em disco sem exigir serviço externo, coerente com a operação
em estação de trabalho única; SQLite guarda os dados relacionais da aplicação. A combinação
atende ao diferencial "Bancos de Dados" sem custo de infraestrutura. PostgreSQL com pgvector
seria a escolha mais convincente como arquitetura industrial definitiva, e está registrado em
`docs/arquitetura.md` como o caminho de evolução — foi preterido apenas pelo custo de
configuração dentro das 72 horas.

**Consequências aceitas.** Sem busca léxica, termos técnicos exatos (`BPFO`, "pé manco")
dependem inteiramente da representação vetorial. O risco é contido pelo filtro por documento
descrito no ADR-004, que reduz o espaço de busca antes da consulta semântica. A busca híbrida
com BM25 fica registrada como melhoria natural.

---

## ADR-010 — Guardrail em duas barreiras: roteamento determinístico e limiar calibrado

**Contexto.** O ADR-004 estabelece que o sistema não responde sem respaldo documental. Resta
definir *como* essa ausência é constatada.

**Alternativas.** (a) limiar de similaridade semântica como único critério; (b) roteamento
determinístico pelo mapa defeito → documento como único critério; (c) as duas barreiras em
sequência.

**Decisão.** Duas barreiras em sequência. A primeira é determinística: o defeito canônico
(ADR-005) é consultado no mapa defeito → documento, artefato versionado e explícito; sem
documento mapeado, o LLM não é acionado e a resposta é a recusa com convite ao cadastro. A
segunda é semântica: havendo documento, a recuperação ainda precisa devolver trechos acima de
um limiar de relevância, **calibrado empiricamente** contra um conjunto de perguntas com
resposta conhecida (defeitos documentados) e sem resposta (`falta_fase`, `ventoinha`).

**Justificativa.** A primeira barreira é impossível de furar porque não envolve modelo algum
— é uma consulta a dicionário, e é ela que garante o comportamento exigido pelo enunciado. A
segunda cobre o caso em que existe documento para o defeito, mas nenhuma seção dele responde
à pergunta específica do técnico. Calibrar o limiar em vez de arbitrá-lo transforma um número
mágico em um número defensável: a resposta a "por que esse corte?" passa a ser "porque separa
os casos documentados dos não documentados no conjunto de calibração", e não uma preferência
pessoal. O procedimento e o resultado ficam registrados no notebook.

**Consequências aceitas.** O conjunto de calibração é pequeno e construído por nós, portanto
o limiar é uma estimativa, não uma garantia. A barreira determinística permanece como piso de
segurança independentemente disso.

---

## ADR-011 — `eccentric_rotor` classificado como defeito sem documentação

**Contexto.** `eccentric_rotor` responde por 16.497 eventos (10,9% do conjunto). Não há
documento dedicado a ele. Existe documentação *adjacente*: a seção 8 do Doc5 trata de
excentricidade, mas de **polia**, e prescreve reinstalar ou substituir a polia; o Doc4 cita
excentricidade apenas como característica de modulação em torno da RPM.

**Alternativas.** (a) mapear para o Doc5, elevando a cobertura de 80,4% para 91,3% dos
eventos de defeito; (b) tratar como sem documentação; (c) entregar o conteúdo do Doc5 com
ressalva de que trata de polia.

**Decisão.** Tratar como defeito sem documentação, seguindo o caminho de recusa do ADR-004.

**Justificativa.** Rotor excêntrico e polia excêntrica são defeitos distintos, em componentes
distintos, com correções distintas — o próprio Doc6, na seção 11, trata o rotor como assunto
separado. Prescrever "reinstale a polia" diante de um rotor excêntrico é precisamente a
alucinação *plausível*: superficialmente pertinente, tecnicamente errada, e capaz de levar um
técnico a intervir no componente errado de um equipamento crítico. Um sistema que recupera
documentação aproximada e a apresenta como resposta não está sendo útil, está terceirizando o
erro para quem o lê. A resposta com ressalva foi descartada por produzir comportamento
inconsistente: o sistema passaria a ter um quarto caminho, "responder com dúvida", difícil de
definir com clareza e ainda mais difícil de defender como regra geral.

Esta decisão é deliberadamente conservadora e assumida como tal. Ela demonstra que o guardrail
não é uma verificação contra uma lista de rótulos conhecidos, mas uma decisão de escopo sobre
o que constitui respaldo documental suficiente.

**Consequências aceitas.** A cobertura documental cai para 80,4% dos eventos de defeito, e um
volume expressivo de eventos recebe recusa em vez de prescrição. É o custo de não errar em
manutenção industrial. Na prática operacional, a resposta correta é a que o sistema já dá:
cadastre o procedimento de rotor excêntrico.

---

## ADR-004 — Guardrail contra alucinação: sem documento, sem recomendação

**Contexto.** O enunciado determina que o sistema se detenha unicamente a problemas que
possuem documentos e, caso contrário, reporte a ausência e sugira o cadastro de um novo
documento. "Alucinação do modelo" é critério explícito de avaliação na entrevista.

**Alternativas.** (a) confiar na instrução do prompt; (b) barreira determinística antes da
geração; (c) verificação posterior da resposta gerada.

**Decisão.** Barreira determinística em código, anterior à chamada do LLM: se a recuperação
documental não retornar trecho algum acima do limiar de relevância para o defeito
identificado, o LLM não é acionado e a resposta padrão de "defeito sem documentação" é
devolvida, junto do convite ao cadastro. Quando há trechos, a resposta é obrigatoriamente
acompanhada das fontes citadas.

**Justificativa.** Instrução em prompt é uma preferência estatística, não uma garantia — um
modelo de 8B a viola sob pressão de contexto. Retirar do modelo a possibilidade de responder
é a única forma de tornar o comportamento verificável. O custo de uma recomendação inventada
em manutenção industrial é uma intervenção errada em equipamento crítico.

**Consequências aceitas.** O sistema recusa alguns casos que talvez pudesse responder. Em
manutenção, "não sei, documente" é uma resposta segura; uma prescrição inventada não é.

---

<!-- Próximos ADRs conforme a implementação avança: modelo de embeddings, estratégia de
     chunking dos documentos, banco de dados, estratégia de deploy. -->

---

## ADR-012 — OCR para o Doc1, digitalizado

**Contexto.** A análise inicial da base documental registrou os seis PDFs como texto nativo
extraível. A verificação com o extrator de fato usado pelo pipeline mostrou outra coisa:

| Documento | Páginas | Caracteres extraíveis | Imagens |
| --- | --- | --- | --- |
| **Doc1** | 17 | **0** | **18** |
| Doc2 | 6 | 7.842 | 0 |
| Doc3 | 10 | 6.228 | 0 |
| Doc4 | 9 | 6.821 | 0 |
| Doc5 | 10 | 6.951 | 0 |
| Doc6 | 10 | 6.879 | 0 |

O Doc1 é um documento digitalizado: cada página é uma imagem, sem camada de texto. A
divergência veio de a inspeção inicial ter sido feita por uma ferramenta que renderiza a
página visualmente, e portanto enxerga conteúdo que nenhum extrator de PDF recupera.

O documento não é dispensável. É o único procedimento que cobre as quatro famílias de falha
de rolamento — `rolamento_inner`, `rolamento_outer`, `rolamento_ball` e
`rolamento_combination` —, somando **60.779 eventos, 40,2% de todos os defeitos** do
histórico. Sem ele, a cobertura documental cai de 80,4% para 40,2% e o guardrail passa a
recusar justamente a família de defeito mais frequente.

**Alternativas.** (a) descartar o Doc1 e tratar rolamentos como sem documentação; (b) OCR com
Tesseract via `pytesseract`; (c) OCR com RapidOCR sobre páginas rasterizadas por `pypdfium2`.

**Decisão.** OCR com RapidOCR (`rapidocr-onnxruntime`) sobre as páginas rasterizadas com
`pypdfium2`, aplicado apenas aos documentos sem camada de texto. A extração escolhe a
estratégia por documento: texto nativo quando existe, OCR quando não existe.

**Justificativa.** Descartar o Doc1 seria abrir mão de 40% da cobertura por limitação de
ferramenta, não por ausência de informação — o procedimento existe e está legível. Entre as
duas rotas de OCR, RapidOCR instala-se inteiramente por `pip` e roda sobre ONNX Runtime em
CPU, sem exigir binário de sistema nem pacote de idioma instalados à parte. Isso importa
duplamente: mantém o repositório reproduzível por quem apenas executa `pip install -r
requirements.txt`, e preserva a premissa de operação offline em rede segregada que sustenta o
ADR-001. Tesseract entrega qualidade equivalente ou superior, mas ao custo de uma dependência
externa ao ecossistema Python.

A situação, aliás, é a realidade de qualquer base documental industrial: procedimentos antigos
existem como digitalizações de papel. O enunciado lista "tratamento dos documentos fornecidos"
como item próprio do desafio, o que sugere que a heterogeneidade é proposital.

**Consequências aceitas.** O OCR introduz ruído de reconhecimento — caracteres trocados,
quebras de linha espúrias — que não existe nos outros cinco documentos. Duas medidas contêm o
efeito: o texto reconhecido é normalizado antes do fatiamento, e a qualidade da extração é
verificada por teste automatizado contra marcadores conhecidos do documento. O processamento
do Doc1 é mais lento que o dos demais e, por isso, o resultado da extração é armazenado em
cache, evitando repetir o OCR a cada execução do pipeline.

---

## ADR-013 — Modelo de linguagem selecionável por ambiente

**Contexto.** O ADR-001 dimensionou o Qwen2.5 7B quantizado para a estação descrita no
enunciado: 32 GB de RAM e GPU de 16 GB dedicados. A máquina em que a solução é desenvolvida e
será demonstrada tem outra configuração — gráficos integrados Intel Iris Xe e 15,7 GB de RAM
—, e o Ollama executa o modelo integralmente em CPU. Medições com a base indexada:

| Modelo | Processamento | Geração (modelo já carregado) |
| --- | --- | --- |
| Qwen2.5 7B Instruct | 100% CPU | 115 s |
| Qwen2.5 3B Instruct | 100% CPU | 32 s |

Na GPU de 16 GB prevista para operação, o 7B responderia em poucos segundos; a lentidão é
consequência do hardware de desenvolvimento, não da arquitetura.

**Alternativas.** (a) manter apenas o 7B e compensar com geração incremental; (b) reduzir o
contexto e o teto de tokens do 7B; (c) tornar o modelo selecionável, com o 7B como padrão de
produção e um modelo menor para hardware sem GPU dedicada.

**Decisão.** O modelo é lido da variável de ambiente `MODELO_LLM`, com o Qwen2.5 7B como
padrão. Um modelo reduzido (Qwen2.5 3B) fica documentado para execução em hardware sem GPU
dedicada. A geração incremental (`responder_em_fluxo`) é oferecida para a interface de chat,
independentemente do modelo escolhido.

**Justificativa.** Reduzir o contexto do 7B foi descartado de imediato: encurtar os trechos
recuperados degrada exatamente aquilo que a solução entrega — a prescrição fundamentada — para
ganhar tempo de máquina. É otimizar a métrica errada.

A separação entre modelo de produção e modelo de execução local é possível justamente pelo
desenho do RAG. Como toda a competência técnica da resposta vem dos trechos recuperados, e não
do que o modelo memorizou, trocar 7B por 3B custa fluência de redação, não conteúdo: as
citações continuam corretas porque são determinadas pela recuperação, que não mudou. Um
sistema que dependesse do conhecimento interno do modelo não toleraria essa troca — o fato de
tolerar é evidência de que o desenho está correto.

Ler o modelo do ambiente também é o que permite dimensionar a instalação por planta, sem
alterar código: uma unidade com servidor de inferência usa o 7B ou maior; uma estação de
manutenção isolada usa o modelo reduzido.

**Consequências aceitas.** Duas configurações a verificar, e respostas de qualidade textual
distinta entre elas. A demonstração declara qual modelo está em uso, e a comparação entre os
dois é, ela própria, material de apresentação: mostra que a arquitetura degrada com elegância
em hardware menor em vez de deixar de funcionar.

---

## ADR-014 — Cobertura documental em duas camadas: mapa versionado e registro operacional

> **Revisão 1 (06/08/2026)** — a consequência aceita registrada abaixo *não estava
> implementada*. O recadastro substituía a linha do SQLite, como afirmado, mas o índice
> vetorial é gravado por `upsert`, que atualiza os ids recebidos e **não apaga os
> ausentes**: um procedimento recadastrado com menos seções que o anterior deixava as
> excedentes recuperáveis, ainda associadas ao mesmo documento. A prescrição passaria a
> citar seção de procedimento revogado — com a aparência de fonte legítima, que é o modo
> de falha que o ADR-004 existe para impedir.
>
> Corrigido com `IndiceDocumental.remover_documento`, chamado antes da indexação em
> `cadastrar`. Na mesma revisão, a ordem dos passos passou a validar o arquivo **antes**
> de gravar: a anterior sobrescrevia o PDF de destino e o apagava ao falhar na extração,
> de modo que um envio inválido destruía o procedimento válido que estava cadastrado.
>
> **Consequência de método.** O teste `test_recadastro_substitui` repetia a frase desta
> seção na docstring e verificava `len(registro) == 1` — a linha do banco relacional, não
> o índice de onde sai a citação. E cadastrava o mesmo arquivo duas vezes, de modo que a
> contagem de seções coincidia e a falha não podia aparecer. O dublê `IndiceFalso`
> acumulava, reproduzindo fielmente o defeito. A regra que fica: **consequência aceita
> declarada em ADR precisa de um teste que a verifique** — e o teste precisa exercitar a
> mudança que ela descreve, não uma repetição idêntica. É o ADR-017 aplicado a
> consequências, e não a afirmações de interface.

**Contexto.** O ADR-010 estabeleceu o mapa defeito → documento como primeira barreira do
guardrail, e o enunciado exige que o sistema, ao recusar, sugira ao usuário registrar um novo
documento para o defeito. Um mapa estático em código torna essa sugestão vazia: o técnico
cadastraria o procedimento e o sistema continuaria recusando o mesmo defeito, porque a
cobertura só mudaria com alteração de código-fonte e novo implante.

**Alternativas.** (a) manter o mapa estático e tratar o cadastro como pedido a ser atendido
manualmente entre versões; (b) migrar a cobertura inteira para banco de dados; (c) manter o
mapa versionado como base e sobrepor a ele um registro persistente dos cadastros feitos em
operação.

**Decisão.** Duas camadas. O mapa em `src/rag/mapeamento.py` permanece estático, versionado e
coberto por testes — descreve a base entregue com o projeto. Um registro em SQLite
(`src/rag/registro.py`) guarda as associações criadas em operação e é consultado pelo roteador
a cada decisão, sobrepondo-se ao mapa quando há cadastro para a condição.

**Justificativa.** As duas camadas respondem a perguntas diferentes. O mapa é uma afirmação
de projeto — "estes procedimentos cobrem estes defeitos, e estes três não têm cobertura, por
estas razões" — e sua estabilidade é o que permite testá-lo e defendê-lo; é dele que sai a
recusa de `eccentric_rotor` do ADR-011. O registro é estado operacional, criado pela equipe de
manutenção em resposta às próprias recusas do sistema, e por natureza muda sem passar por
revisão de código.

Migrar tudo para o banco apagaria essa distinção e, com ela, a possibilidade de verificar por
teste que `falta_fase` não tem documento: a asserção passaria a depender do conteúdo de um
banco mutável. Manter tudo em código, por outro lado, transformaria o convite ao cadastro em
promessa não cumprida — o defeito mais grave possível em um sistema cuja tese é justamente não
prometer o que não pode entregar.

A consulta ao registro acontece a cada decisão, e não na inicialização do roteador, para que o
documento recém-cadastrado valha na consulta seguinte. Isso é o que permite demonstrar o ciclo
completo — recusa, cadastro, atendimento — sem reiniciar o serviço.

**Consequências aceitas.** Duas fontes de verdade para a cobertura, com precedência definida
(registro sobre mapa) e teste de ciclo completo garantindo que a composição funciona. Um
recadastro para a mesma condição substitui o anterior em vez de acumular: manter as duas
versões faria a busca recuperar procedimento obsoleto sem que ninguém percebesse.

---

## ADR-010-A — Revisão da segunda barreira após medição em uso realista

> Complementa o ADR-010. A decisão original — duas barreiras, com a segunda calibrada
> empiricamente — permanece. O que mudou foi o conjunto de calibração, a formulação da
> consulta e o valor do corte, depois que o comportamento em chat expôs uma falha do método
> original.

**Contexto.** A primeira calibração usou 30 perguntas longas e bem formuladas e produziu
separação perfeita entre pertinentes (a partir de 0,8728) e impertinentes (até 0,8409), com
corte em 0,8569. O número parecia sólido.

Ao exercitar o endpoint de chat, uma pergunta legítima foi recusada: *"o eixo pode estar
empenado?"*, dirigida a um evento de `cocked_rotor`, cujo Doc6 tem uma seção inteira sobre
inspeção do eixo. A medição explicou o motivo:

| Pergunta curta legítima | Relevância |
| --- | --- |
| o eixo pode estar empenado? | 0,8395 |
| o rolamento está ruim? | 0,8493 |
| e o rolamento? | 0,8131 |
| como alinho? | 0,8009 |

Todas abaixo do corte de 0,8569 — e abaixo de impertinentes bem formuladas, como *"como
corrigir a cavitação da bomba centrífuga"* (0,8409). **O comprimento do texto domina a
similaridade de cosseno.** Comparar uma pergunta de três palavras com uma seção inteira de
procedimento mede sobretudo a diferença de tamanho, não a pertinência.

O conjunto de calibração original não representava o uso real: ninguém digita "qual o
procedimento para substituir um rolamento danificado" num chat, digita "e o rolamento?".

**Decisão.** Três mudanças:

1. **Consulta ancorada na condição.** O texto enviado ao índice passa a ser
   `"{condição}: {pergunta}"`, devolvendo à consulta a massa semântica que a conversa deixa
   implícita — o técnico não repete "rotor inclinado" a cada frase porque o assunto já está
   estabelecido, e o sistema conhece a condição pelo evento.
2. **Conjunto de calibração ampliado** para 44 perguntas, metade longas e metade curtas, dos
   dois lados, medidas com a mesma transformação usada em produção.
3. **Limiar em 0,8400**, operando como piso.

**Justificativa.** Com o conjunto realista, as distribuições passam a se sobrepor: as
pertinentes começam em 0,8407 e as impertinentes chegam a 0,8646. Nenhum corte acerta os dois
lados:

| Limiar | Legítimas aceitas | Impertinentes barradas |
| --- | --- | --- |
| **0,8400** | **24/24** | 10/20 |
| 0,8500 | 22/24 | 15/20 |
| 0,8590 | 19/24 | 19/20 |

A escolha do piso decorre do papel desta barreira, que a primeira medição havia
superestimado. O caso central — defeito sem procedimento algum — é resolvido pela primeira
barreira, determinística e imune a formulação. A segunda trata apenas de "defeito documentado
com pergunta fora do assunto", e o que escapa dela ainda encontra duas defesas: o modelo
recebe exclusivamente trechos do documento roteado, e a instrução de sistema exige que
declare quando o procedimento não cobre o ponto.

Diante disso, uma recusa indevida custa mais do que uma passagem indevida. A recusa indevida
é visível, frustra o técnico diante de uma pergunta pertinente e ensina a não confiar no
sistema; a passagem indevida entrega uma resposta que, no pior caso, informa que o
procedimento não trata do assunto.

**Consequências aceitas.** A segunda barreira barra metade das perguntas fora de escopo, não a
totalidade. A busca híbrida com BM25, já registrada no ADR-009 como evolução natural,
atacaria exatamente esta limitação: termos técnicos exatos dariam ao sinal léxico a
discriminação que o comprimento do texto rouba do sinal semântico.

**Reprodutibilidade (05/08/2026).** `scripts/calibrar_limiar.py` passou a codificar este
critério. Até então ele maximizava um escore **simétrico** — fração de pertinentes aceitas
mais fração de impertinentes barradas — e devolvia **0,8590**, contradizendo o 0,8400 que o
código aplicava: quem executasse o procedimento de calibração obtinha um número diferente do
que o sistema usa. O critério simétrico trata os dois erros como igualmente caros, que é
exatamente a premissa rejeitada acima. Com o piso codificado, o script devolve 0,8403 —
0,8400 é esse valor arredondado para baixo — e aceita 24/24 barrando 10/20, reproduzindo a
tabela desta decisão.

Registra-se também o método: a primeira calibração não estava errada por descuido de execução,
e sim por medir um uso que não era o real. Um número obtido com rigor sobre o conjunto errado
continua sendo o número errado.

---

## ADR-015 — Design system com verificação automática, em vez de convenção

**Contexto.** Depois de construída a interface React, um levantamento nos componentes
encontrou **vinte e duas medidas de texto distintas** — 0,66rem, 0,70, 0,71, 0,72, 0,74,
0,76, 0,78, 0,79, 0,80, 0,81, 0,82, 0,83, 0,84, 0,86, 0,88, 0,90, 0,92, 0,95, 1,00, 1,60,
1,70 —, todas escritas como valor arbitrário no ponto de uso (`text-[0.79rem]`). O mesmo
valia para raios (`rounded-lg`, `rounded-[10px]`, `rounded-[12px]`, `rounded-xl`), para
tamanhos de ícone passados como número e para os eixos dos gráficos, em 10px e 11px, que não
correspondiam a degrau algum.

Nenhum desses valores era decisão. Eram ajustes locais, cada um razoável no momento em que
foi escrito e nenhum defensável depois. Uma escala tipográfica de sete degraus chegou a ser
declarada em `index.css`, mas **nenhum componente a consumia**: existia como documentação de
uma intenção que o código não seguia.

**Alternativas.** (a) manter a escala como convenção documentada e confiar na disciplina de
quem edita; (b) migrar para uma biblioteca de componentes que já traga um sistema pronto;
(c) declarar os tokens e verificar a conformidade automaticamente na compilação.

**Escolha.** (c). `web/src/index.css` passa a ser a única fonte de verdade da aparência — cor,
tipografia, raio, dimensão de layout, sombra e tempo de transição —, e
`web/scripts/verificar-tokens.mjs` roda dentro de `npm run build`, reprovando o pacote se
qualquer arquivo em `src/` reintroduzir medida absoluta, cor literal, `text-white`, escala de
cor do Tailwind ou tamanho de fonte numérico.

**Justificativa.** A alternativa (a) é exatamente o que já havia sido tentado, e o resultado
está medido acima: a escala existia e foi ignorada. Um design system que depende de disciplina
se dissolve na primeira pressa, e este projeto tem prazo. A alternativa (b) traria dezenas de
variantes não usadas e, pior para a entrevista, substituiria decisões explicáveis por padrões
de terceiros — não se defende o que não se escolheu.

A verificação automática muda a natureza da regra: deixa de ser recomendação e passa a ser
condição de build. O custo é um arquivo de cem linhas; o retorno é que a próxima medida solta
não chega ao produto.

Três pontos mereceram tratamento específico:

1. **Os gráficos.** O Recharts recebe tamanho de fonte e altura como números em JavaScript,
   onde `fontSize: 11` não é sintaxe de CSS e escaparia a qualquer verificador textual.
   `componentes/graficos.tsx` **lê os próprios tokens do documento** em tempo de execução, em
   vez de repeti-los — não há como a escala do CSS e a dos gráficos divergirem.
2. **As sombras.** O Tailwind resolve tokens de sombra em tempo de compilação e assa o valor
   do tema claro dentro da classe. Usar `shadow-cartao` teria eliminado silenciosamente a
   sombra do tema escuro, que é bem mais opaca porque superfície escura precisa disso. As
   sombras são citadas por `var()`, com o motivo registrado no código.
3. **A marca.** O quadrado do logotipo usava `bg-tinta` com ícone branco. No tema escuro
   `--color-tinta` inverte para um cinza claro, e o ícone branco desaparecia sobre ele. Ganhou
   token próprio, `--color-marca`, porque é a única cor do produto que não pertence à rampa de
   tinta.

**Consequências aceitas.** Valores arbitrários que citam token (`w-[var(--largura-lateral)]`),
percentuais e frações de grade continuam permitidos — são relação, não medida. O verificador é
textual e não entende o código: um valor escondido atrás de concatenação de string passaria.
Aceita-se, porque o alvo não é o adversário determinado, e sim o próprio autor com pressa.


---

## ADR-016 — Modelo fora do ar é 503, não 500

**Contexto.** Durante a preparação da demonstração, com o Ollama parado, o caminho de
prescrição devolvia **HTTP 500** e a interface exibia *"A API não está respondendo — suba a
API: `uvicorn src.api.app:app`"*. As duas afirmações eram falsas: a API respondeu, e o
processo a reiniciar era outro. Numa demonstração ao vivo, isso manda o apresentador digitar
o comando errado enquanto o problema real continua de pé.

O detalhe agravante é que **o sistema já sabia**: `Gerador.disponivel()` existia e
`GET /sistema` já publicava `modelo_disponivel`. A informação estava computada, exposta — e
descartada pelo caminho de requisição.

**Alternativas.** (a) manter 500 e melhorar apenas o texto na interface; (b) verificar a
disponibilidade na entrada de toda rota que possa gerar; (c) traduzir a falha em 503 com
mensagem própria, verificando de forma preguiçosa no caminho bloqueante e ansiosa no fluxo.

**Escolha.** (c). Uma exceção de domínio, `ModeloIndisponivel`, é traduzida por um
`exception_handler` da aplicação em **503 com `Retry-After: 10`**.

**Justificativa.** A API é o contrato de integração (ADR-002), e o código de status é a
parte do contrato que um supervisório ou CMMS lê primeiro. `500` significa defeito não
tratado no servidor — vira chamado de suporte. `503` significa dependência indisponível e é
retentável por convenção. Devolver 500 para uma condição prevista e recuperável mente sobre
a natureza da falha.

Descartou-se (a) porque o problema não é de texto: um segundo cliente da API, sem interface
nenhuma, continuaria recebendo a informação errada. Descartou-se (b) porque verificar na
entrada da rota tornaria as **recusas** dependentes do modelo estar no ar — exatamente o
acoplamento que o ADR-004 existe para impedir.

Duas sutilezas de implementação ficaram registradas no código:

1. **`responder_em_fluxo` deixou de ser uma função geradora.** Sendo geradora, nada dentro
   dela executava até o primeiro `next()` — que, na API, acontece **depois** de os
   cabeçalhos terem sido enviados, quando devolver 503 já é impossível. Passou a ser uma
   função comum que verifica e *retorna* um gerador.
2. **A mensagem distingue os dois motivos** — serviço parado (`ollama serve`) e modelo não
   baixado (`ollama pull`) —, porque a ação corretiva é diferente e uma mensagem genérica
   mandaria conferir a coisa errada.

**Consequência que virou argumento.** Com o modelo derrubado, **três dos quatro caminhos
seguem respondendo 200**: as duas recusas e o estado operacional. Não é tolerância a falha
acidental — é o ADR-004 se verificando sob estresse, já que os textos de recusa são
compostos em código e nunca gerados. `tests/test_api_modelo_fora.py` afirma isso
explicitamente: se um dia essas rotas passarem a depender do LLM, o teste falha.

A tela passou a dizê-lo: *"as verificações documentais seguem ativas — o sistema continua
recusando o que não tem respaldo; só não consegue redigir a prescrição"*.

---

## ADR-017 — As campanhas de ensaio, medidas corretamente

**Contexto.** O painel exibia, sob a série temporal, a frase: *"Cada campanha de ensaio
concentra um modo de falha, em janelas quase disjuntas. É por isso que a data não entra como
atributo do modelo: ela prediz o rótulo por construção."*

Ao implementar as faixas de campanha no gráfico, a estatística disponível era
`janelas_por_condicao` — primeiro e último evento de cada condição. Medida assim, a
afirmação **é falsa**: `desbalanceado` é ensaiado no fim de abril e reaparece em junho, de
modo que sua janela cobre os 47 dias inteiros e se sobrepõe a todas as outras. Desenhar as
faixas com esse dado teria produzido doze retângulos empilhados cobrindo o gráfico — a
refutação visual da legenda logo abaixo.

**Investigação.** A concentração existe, mas no dia, não na janela. Medindo a condição que
domina cada um dos 29 dias com defeito:

| | dominância diária |
| --- | --- |
| 30/04 – 28/05 | 61% a 100% — dez blocos, um modo de falha por vez |
| 01/06 – 16/06 | 22% a 63% — campanhas sobrepostas |

Mediana de 74%, com 9 dias de condição única e 8 de apenas duas. São **18 blocos contíguos**
de mesma condição dominante.

**Escolha.** `janelas_por_condicao` foi substituída por `campanhas: list[BlocoDeCampanha]` —
trechos contíguos de dias com a mesma condição dominante, cada um carregando a `dominancia`
média. O campo antigo era, além de enganoso, **código morto**: estava declarado e nenhum
consumidor o lia.

A legenda do gráfico passou a afirmar o que foi medido, incluindo o segundo regime.

**Justificativa.** O argumento do ADR-003 não precisava do exagero e fica mais forte sem
ele. Bastava dizer que a data carrega informação sobre o rótulo — o que os dois regimes
sustentam — para explicar por que a validação por amostragem aleatória infla a acurácia de
11% para 87%. Afirmar "janelas disjuntas" diante de uma banca que pode abrir o CSV era
apostar em ninguém conferir.

**Consequência de método.** O erro sobreviveu porque a frase foi escrita a partir de uma
impressão da análise exploratória e nunca reconferida contra uma estatística. A regra que
fica: **afirmação numérica exibida na interface precisa vir de um campo calculado**, não de
texto redigido — e é por isso que o intervalo, os percentuais e o número de blocos agora
saem todos da API.

**Como as faixas são desenhadas.** Alternância neutra, sem cor por condição, com rótulo
apenas nos blocos de dois dias ou mais. Colorir dezoito campanhas exigiria quatorze cores
novas e destruiria o significado das quatro que existem — é a política de séries categóricas
registrada em `index.css` aplicada ao seu primeiro caso real.
