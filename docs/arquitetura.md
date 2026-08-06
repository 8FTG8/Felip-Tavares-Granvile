# Arquitetura

Solução de manutenção prescritiva: recebe um evento de sensor de vibração, localiza
ocorrências semelhantes no histórico e prescreve a ação corretiva **apenas quando existe
procedimento técnico que a fundamente**.

O porquê de cada escolha está em [`decisoes.md`](decisoes.md) — 18 registros. Este documento
descreve o *que* e o *como*.

---

## 1. Visão geral

```
  evento JSON                                   ┌─ storage/chroma      índice vetorial
       │                                        ├─ storage/documentos  PDFs cadastrados
       ▼                                        └─ storage/registro.db SQLite
┌──────────────┐
│     API      │──── similaridade k-NN ───────► 157.057 vetores · 16 atributos
│   FastAPI    │
│              │──── roteador ──── 1ª barreira: mapa defeito → documento
└──────┬───────┘              └─── 2ª barreira: limiar de relevância 0,8400
       │                                │
       │                                ▼ (só se ambas passarem)
       │                        recuperação → geração (Ollama, local)
       ▼
  interface React          ← cliente HTTP, sem lógica de domínio
```

Duas fronteiras importam:

- **A API é o contrato.** A interface não importa nenhum módulo de `src/`. Um supervisório
  ou CMMS consome os mesmos sete endpoints.
- **O LLM fica atrás das barreiras.** Ele nunca é a primeira coisa a rodar, e nos caminhos
  de recusa não é chamado — asserção verificada em teste.

---

## 2. Camadas

Grafo de dependências sem ciclos. `ingestion` é a base; nada abaixo dela.

| Módulo | Linhas | Responsabilidade |
| --- | ---: | --- |
| `ingestion/rotulos.py` | 159 | 151 grafias → 17 formas canônicas |
| `ingestion/eventos.py` | 105 | carga, descarte de 7 colunas redundantes, marcação de saturação |
| `similarity/indice.py` | 309 | k-NN sobre 16 atributos padronizados |
| `rag/documentos.py` | 254 | extração (nativa ou OCR) e fatiamento por seção |
| `rag/indice_documental.py` | 177 | ChromaDB + `multilingual-e5-large` |
| `rag/mapeamento.py` | 127 | mapa defeito → documento (1ª barreira) |
| `rag/roteador.py` | 215 | decide o caminho de resposta |
| `rag/gerador.py` | 319 | prompt, geração, textos de recusa |
| `rag/registro.py` | 122 | documentos cadastrados em operação (SQLite) |
| `rag/cadastro.py` | 100 | upload → extração → indexação |
| `api/` | 997 | rotas, esquemas, agregações do painel |

Interface em `web/` — React 19 + Vite + TypeScript + Tailwind v4.

---

## 3. O caminho de um evento

```
POST /eventos/analisar  { …16 grandezas…, "fault": "cocked_rotor_2" }
   │
   ├─ normalização        cocked_rotor_2 → cocked_rotor (defeito)
   ├─ k-NN                10 vizinhos, contagem, distribuição temporal, frequência
   │
   ├─ 1ª barreira         MAPA["cocked_rotor"] → "Doc6"        ausente ⇒ recusa
   ├─ recuperação         4 trechos do Doc6, filtrado por documento
   ├─ 2ª barreira         melhor relevância ≥ 0,8400           abaixo ⇒ recusa
   │
   └─ geração             Qwen2.5, temperatura 0,2, só trechos do Doc6
```

**Quatro caminhos de resposta**, decididos antes de qualquer geração:

| Caminho | Quando | LLM é chamado? |
| --- | --- | :---: |
| `prescricao` | defeito documentado, trecho relevante | sim |
| `sem_documento` | defeito sem procedimento, ou nenhum trecho relevante | **não** |
| `estado` | é estado operacional, não falha | **não** |
| `sem_condicao` | rótulo ausente na entrada | **não** |

O contexto histórico do k-NN é devolvido nos quatro. Mesmo sem prescrição a recomendar,
saber quantas vezes o padrão ocorreu é informação útil.

---

## 4. As duas barreiras

O critério "Alucinação do modelo" é o motivo desta seção existir.

**1ª — mapa defeito → documento.** Consulta a dicionário. Sem modelo, sem embedding, sem
parâmetro. Nenhuma formulação de pergunta a contorna. Cobre o caso central do enunciado:
defeito sem procedimento não recebe recomendação.

**2ª — limiar de relevância.** Cobre o caso fino: o documento existe, mas nenhuma seção
responde à pergunta. Calibrada empiricamente sobre 44 perguntas de resposta conhecida —
procedimento em [`notebooks/02-calibracao-do-limiar.ipynb`](../notebooks/02-calibracao-do-limiar.ipynb).

Três propriedades sustentam o conjunto:

1. **Os textos de recusa são compostos em código, nunca gerados.** Uma recusa escrita pelo
   modelo poderia alucinar a própria justificativa.
2. **O modelo recebe exclusivamente trechos do documento roteado.** Não há de onde inventar.
3. **A instrução de sistema exige declarar** quando o procedimento não cobre o ponto
   perguntado.

Verificação sob falha: com o Ollama derrubado, os caminhos de recusa e de estado continuam
respondendo `200` — `tests/test_api_modelo_fora.py`.

---

## 5. Armazenamento

| Onde | O quê | Tamanho |
| --- | --- | ---: |
| `docs/dados/banner.csv` | histórico de eventos, versionado | 31 MB |
| `storage/chroma/` | 115 trechos vetorizados | 1,6 MB |
| `storage/documentos/` | PDFs cadastrados em operação | 148 KB |
| `storage/registro.db` | SQLite: quais defeitos ganharam procedimento | 12 KB |

**Cobertura documental em duas camadas.** O mapa em código é versionado e revisável; o
registro SQLite recebe o que for cadastrado em operação. O roteador consulta os dois a cada
decisão — documento cadastrado passa a valer sem reiniciar o serviço.

---

## 6. Custos medidos

Medidos nesta máquina de desenvolvimento (Intel Iris Xe, 15,7 GB de RAM, sem GPU dedicada).

**Memória residente do processo da API**

| Etapa | Acumulado |
| --- | ---: |
| Python | 17 MB |
| \+ 166.796 eventos | 132 MB |
| \+ índice k-NN | 263 MB |
| \+ `multilingual-e5-large` | ~1,9 GB |

O modelo de embeddings responde por ~1,8 GB e carrega **tardiamente** — na primeira busca
semântica, não na subida do serviço.

**Latência**

| Operação | Tempo |
| --- | ---: |
| Ajuste do índice k-NN (uma vez, na subida) | 1,2 s |
| Consulta k-NN | **21 ms** |
| Carga do `e5` (uma vez, na 1ª busca) | 9,2 s |
| Busca semântica | 115 ms |
| **Decisão de recusa (1ª barreira)** | **~0 ms** |
| Decisão completa (2 barreiras + recuperação) | 105 ms |
| Geração — Qwen2.5 3B, **em CPU** | ~32 s |
| Geração — Qwen2.5 7B, **em CPU** | ~115 s |

A recusa custa uma consulta a dicionário. É o que torna o guardrail barato o bastante para
ser sempre aplicado.

---

## 7. Dimensionamento na estação de referência

Restrição do enunciado: até **32 GB de RAM e GPU de 16 GB**.

| Componente | RAM | VRAM |
| --- | ---: | ---: |
| API (eventos + k-NN + e5) | ~2 GB | — |
| Ollama, Qwen2.5 7B quantizado | — | ~4,7 GB |
| Interface (estático servido por nginx) | ~0 | — |
| **Total** | **~2 GB** | **~4,7 GB** |

Sobra folga em ambos. As margens permitem manter o modelo residente entre requisições, subir
um modelo maior (14B ocuparia ~9 GB de VRAM) ou crescer o histórico — 166.796 eventos ocupam
115 MB, então anos de operação cabem sem mudar de estratégia.

**O gargalo é a geração, e só ela.** Nesta máquina, em CPU, são 32 s a 115 s; na estação com
GPU de 16 GB, segundos. Todo o resto — k-NN, roteamento, recuperação — soma menos de 130 ms.

---

## 8. Implantação

> **O que existe:** o empacotamento em `docker-compose.yml` — três serviços, descritos ao
> final desta seção. **O que é proposta:** o caminho do dado a partir dos sensores
> (MQTT/OPC-UA, broker, adaptador), que não está implementado. O diagrama abaixo mostra os
> dois, e o texto diz qual é qual.

```
   ┌─────────── proposta, não implementada ───────────┐ ┌──── docker-compose.yml ────┐
    sensores ──MQTT/OPC-UA──► broker ──► adaptador ──HTTP──► api ──► ollama
     (chão)                (Mosquitto)  (normaliza)      (uvicorn)  (modelos)
                                                            ▲
   ╰──────────── rede OT, segregada ─────────────╯          │  web (nginx: estático + /api)
                                                     rede TI ╯  ──► CMMS/supervisório
```

### O que está implementado

**Três serviços.** `api` (uvicorn), `web` (nginx servindo o build estático e encaminhando
`/api`) e `ollama` (volume próprio para os modelos). O nginx reproduz em produção o proxy
que o `vite.config.ts` monta em desenvolvimento — mesma origem, sem CORS, e a interface
chama as mesmas URLs nos dois ambientes.

O **broker ficou de fora**. Não existe adaptador que publique ou consuma dele, e subir um
broker inerte seria encenar uma integração que não foi feita.

**Estado que sobrevive ao contêiner.** `storage/` em volume nomeado — índice vetorial,
registro SQLite e os PDFs cadastrados em operação (ADR-014). Mais dois volumes que evitam
repetir download: o do `multilingual-e5-large` (~2,2 GB) e o dos modelos do Ollama.

**Dados por montagem, não por imagem.** `docs/dados/` entra como volume somente leitura:
os 31 MB do `banner.csv` não pertencem à imagem. `data/` entra gravável, para preservar o
cache do OCR do Doc1 entre execuções.

**O modelo é baixado à parte**, com `ollama pull`, e não durante o `up` — são 2 GB a
4,7 GB que travariam a subida sem explicar o motivo.

### O que é proposta

**Caminho do dado.** Sensores publicam em MQTT (ou OPC-UA, conforme o CLP). Um adaptador
consome do broker, converte o payload para o esquema de `POST /eventos/analisar` e chama a
API. O adaptador é o único componente novo, e é fino — a normalização de rótulo já é da API.

**Segregação de rede.** O broker fica na rede OT; a API, na TI. O tráfego atravessa numa
direção só, e nenhum dado sai da planta: modelo de linguagem e embeddings são locais, que é
a razão registrada no ADR-001.

**Operação contínua.** O índice k-NN é reconstruído na subida (1,2 s). Com o histórico
crescendo, a evolução natural é persistir os vetores em vez de reajustar.

---

## 9. Evolução

Em ordem de retorno, com o gatilho que justificaria cada uma:

| Evolução | Gatilho | Por quê |
| --- | --- | --- |
| **Busca híbrida BM25 + semântica** | já justificável | a 2ª barreira barra ~metade das perguntas fora de assunto; termo técnico exato daria ao sinal léxico a discriminação que o comprimento do texto rouba do semântico (ADR-009) |
| **PostgreSQL + pgvector** | dois ou mais nós de API | unifica eventos, registro e vetores num armazenamento transacional; hoje são três lugares porque um processo só os coordena |
| **Índice k-NN persistido** | histórico acima de ~1 M eventos | evita reajustar na subida |
| **Modelo maior (14B)** | se a qualidade da redação limitar | cabe na VRAM de 16 GB com folga |
| **Realimentação do técnico** | com uso real | registrar quando a prescrição foi útil dá o dado que hoje não existe para avaliar qualidade de resposta |

**O que deliberadamente não está no caminho crítico:** classificador de defeito. O rótulo vem
anotado na entrada, e um classificador sobre os atributos rende ~12% fora de sessão contra
11,7% de chutar a classe majoritária — evidência em
[`notebooks/01-classificador-e-vazamento.ipynb`](../notebooks/01-classificador-e-vazamento.ipynb).

---

## 10. Qualidade

| Verificação | Comando | Cobre |
| --- | --- | --- |
| Testes | `pytest -m "not lento"` | 253 testes, ~5 s |
| Testes com Ollama real | `pytest` | inclui geração ponta a ponta |
| Tipos, estilo e contraste | `cd web && npm run build` | TypeScript, design system, WCAG 2.1 AA |

Duas verificações merecem nota por serem incomuns:

- **`npm run tokens`** reprova valor de estilo escrito fora do design system — e, na direção
  oposta, token declarado que ninguém consome.
- **`npm run contraste`** mede os 20 pares de cor que ocorrem na interface, lendo os valores
  do próprio CSS. O arquivo afirma que as cores foram medidas; a afirmação é executável.
