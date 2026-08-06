# Manutenção Prescritiva — Estudo de Caso FIESC 02198/2026

Solução de manutenção prescritiva para máquinas rotativas: recebe um evento de sensor de
vibração, localiza ocorrências históricas semelhantes, identifica o tipo de defeito e
prescreve a ação corretiva com base na documentação técnica da empresa — **recusando-se a
responder quando não existe documento para o defeito identificado**.

## O problema em uma frase

Não basta saber *quando* a máquina vai falhar (preditiva); é preciso dizer *o que fazer*
a respeito (prescritiva), com respaldo documental rastreável.

## Arquitetura

```
                        evento JSON (sensor)
                                 │
                                 ▼
                  ┌──────────────────────────┐
                  │        API (FastAPI)     │
                  └────────────┬─────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
      similaridade (k-NN)              roteador do guardrail
   16 atributos padronizados        ┌──────────┴──────────┐
   166.796 eventos, 21 ms           │                     │
              │              1ª barreira            2ª barreira
              │           mapa defeito→doc      limiar de relevância
              │            (dicionário)          calibrado, 0,8400
              │                     │                     │
              │                     └──────────┬──────────┘
              │                                ▼
              │                    ┌───────────────────────┐
              │                    │  recuperação (ChromaDB) │
              │                    │  multilingual-e5-large  │
              │                    └───────────┬───────────┘
              │                                ▼
              │                     geração (Qwen2.5 · Ollama)
              │                    só neste caminho; nunca nos outros
              │                                │
              └────────────────┬───────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────────┐
   │  prescrição fundamentada        ·  seções citadas          │
   │  "sem procedimento cadastrado"  ·  cadastre um documento   │
   │  "estado operacional"           ·  não é falha             │
   └───────────────────────────┬───────────────────────────────┘
                               ▼
                    Interface (React + Vite)
          painel · análise · assistente · base documental
```

Detalhamento em [docs/arquitetura.md](docs/arquitetura.md), incluindo a proposta de
implantação em ambiente industrial.

## O guardrail

É a peça central da solução, e o critério "Alucinação do modelo" do edital é o motivo dela
existir. São **duas barreiras, ambas anteriores a qualquer geração de texto**:

1. **Mapa defeito → documento.** Consulta a dicionário. Não envolve modelo algum e não há
   formulação de pergunta capaz de contorná-la.
2. **Limiar de relevância**, calibrado empiricamente em 0,8400 sobre 44 perguntas reais
   (ADR-010 e ADR-010-A).

Os textos de recusa são **compostos em código, nunca gerados** — uma recusa escrita pelo
modelo poderia alucinar a própria justificativa. Os testes afirmam que o cliente do LLM
recebe **zero chamadas** nos caminhos de recusa, e `tests/test_api_modelo_fora.py` verifica
a consequência disso sob falha: com o Ollama derrubado, três dos quatro caminhos continuam
respondendo normalmente.

## Decisões técnicas

Cada decisão relevante está registrada em [docs/decisoes.md](docs/decisoes.md), no formato
contexto → alternativas → escolha → justificativa → consequências aceitas. São 18 registros;
os principais:

| Decisão | Escolha | Porquê |
| --- | --- | --- |
| LLM | Qwen2.5 Instruct, local via Ollama | Cabe na GPU de 16 GB e opera offline — o dado industrial não sai da planta (ADR-001, ADR-013) |
| Camada de serviço | FastAPI, com a interface como cliente HTTP | O consumidor natural em ambiente industrial é o supervisório, não um navegador: a API é o contrato de integração (ADR-002) |
| Identificação do defeito | Rótulo do operador, normalizado deterministicamente | O `fault` vem no JSON de entrada; um classificador sobre os atributos fica no nível do baseline fora de sessão — 12,4% contra 11,7% de chutar a classe majoritária (ADR-003) |
| Normalização | 151 grafias → 17 formas canônicas | Sem ela o guardrail recusaria 421 eventos que têm documentação (ADR-005) |
| Busca por similaridade | k-NN global, com o defeito de cada vizinho exibido | Responde ao que o enunciado pede e é explicável: a resposta *é* a lista de vizinhos (ADR-008) |
| Recuperação documental | Fatiamento por seção numerada, `multilingual-e5-large`, ChromaDB | Procedimentos passo a passo chegam inteiros e a citação fica verificável (ADR-009) |
| Anti-alucinação | Duas barreiras, ambas antes do LLM | A primeira é consulta a dicionário — impossível de furar por formulação (ADR-004) |
| Falha de dependência | Modelo fora do ar devolve 503, não 500 | 500 diz ao integrador que o serviço tem defeito; 503 diz que a dependência caiu, e é retentável (ADR-016) |

## API

Sete rotas, com OpenAPI publicado em `/docs`:

| Método | Rota | O que faz |
| --- | --- | --- |
| `POST` | `/eventos/analisar` | Pipeline completo; aceita o JSON do enunciado com as colunas redundantes |
| `POST` | `/chat` | Consulta livre, sujeita às mesmas barreiras |
| `POST` | `/chat/fluxo` | Idem, com a resposta transmitida em partes e o roteamento nos cabeçalhos |
| `POST` | `/documentos` | Cadastro de procedimento em operação, sem reiniciar o serviço (ADR-014) |
| `GET` | `/documentos/cobertura` | Situação documental de cada defeito, com justificativa das lacunas |
| `GET` | `/estatisticas` | Panorama do histórico e campanhas de ensaio (ADR-017) |
| `GET` | `/sistema` | Modelo em uso, disponibilidade, limiar e tamanho dos índices |

## Interface

React 19 + Vite + TypeScript + Tailwind v4, em `web/`. Consome exclusivamente a API — não
importa módulo algum do domínio, e nenhuma regra de decisão vive nela.

O design system está inteiro em `web/src/index.css` e é **verificado na compilação**:
`npm run tokens` reprova medida absoluta, cor literal, opacidade fora dos degraus e token
declarado que ninguém consome; `npm run contraste` mede os 20 pares de cor que ocorrem na
interface contra o mínimo da WCAG 2.1 AA, lendo os valores do próprio CSS. Ambos rodam
dentro do `npm run build`. O raciocínio está no ADR-015.

## Dados

O conjunto completo é `docs/dados/banner.csv` — 166.796 eventos, 31 MB —, distribuído pelo
Google Drive indicado no enunciado e, por ora, versionado aqui junto com os seis
procedimentos em PDF.

O repositório traz também uma **amostra estratificada por rótulo bruto** em
`data/amostra_banner.csv` (5.120 eventos, os 151 rótulos representados), que permite rodar
a suíte de testes sem carregar o arquivo inteiro:

```bash
python scripts/gerar_amostra.py    # regenera a amostra a partir do arquivo completo
```

O arquivo `banner.xlsx` distribuído junto **não deve ser usado**: seus valores decimais estão
corrompidos de forma intermitente (`0.0427` gravado como `427.0`, misturando texto e número
na mesma coluna). O CSV é a única fonte confiável, e o motivo está registrado no cabeçalho
de `src/ingestion/eventos.py`.

## Estrutura do repositório

```
data/          amostra estratificada dos eventos
docs/          decisões técnicas, arquitetura e os dados originais
  dados/       os 6 procedimentos em PDF, o enunciado e o banner.csv completo
scripts/       geração da amostra e calibração do limiar do guardrail
src/
  ingestion/   carga dos eventos e normalização canônica dos rótulos
  similarity/  índice k-NN e busca por ocorrências semelhantes
  rag/         ingestão documental, roteador do guardrail e geração
  api/         camada FastAPI e agregações do painel
storage/       índice vetorial, PDFs cadastrados em operação e SQLite (gerados)
tests/         249 testes automatizados
web/           interface React
  src/         telas, componentes e o design system
  scripts/     verificadores de tokens e de contraste
```

## Como executar

**Pré-requisitos:** Python 3.12, Node 22 e [Ollama](https://ollama.com).

A primeira execução baixa **~9 GB** e leva alguns minutos: os dois modelos do Ollama
(2 GB + 4,7 GB) e o modelo de embeddings `multilingual-e5-large` (~2,2 GB), que o
`sentence-transformers` busca sozinho na primeira busca semântica. Depois disso tudo fica
em cache local e a solução opera **sem rede**.

```bash
# 1. Ambiente Python
python -m venv .venv
.venv\Scripts\activate                      # Windows
pip install -r requirements.txt

# 2. Modelo de linguagem
ollama pull qwen2.5:3b-instruct             # 2 GB, para demonstração em CPU
ollama pull qwen2.5:7b-instruct             # 4,7 GB, o modelo de produção
ollama serve

# 3. API — monta os índices no primeiro acesso
#    OCR do Doc1 (digitalizado, 17 páginas) ~1 min, uma vez só; depois fica em cache.
#    A primeira busca semântica ainda baixa o modelo de embeddings, se for a primeira vez.
set MODELO_LLM=qwen2.5:3b-instruct          # opcional; o padrão é o 7B
uvicorn src.api.app:app --port 8000

# 4. Interface, em outro terminal
cd web && npm install && npm run dev
```

A interface fica em `http://localhost:5173` e encaminha `/api` para a porta 8000, o que
dispensa CORS e reproduz o arranjo de produção. A documentação interativa da API fica em
`http://localhost:8000/docs`.

Sem o Ollama no ar a solução continua utilizável: o painel, a busca por similaridade e os
dois caminhos de recusa funcionam normalmente — apenas a redação da prescrição fica
indisponível, e a interface diz exatamente isso.

## Verificação

```bash
pytest -m "not lento"        # 249 testes, ~5 s
pytest                       # inclui os que exercitam o Ollama real
cd web && npm run build      # tipos, tokens de estilo e contraste WCAG
```

## Restrições atendidas

- Implementação integralmente em Python.
- Inferência, consultas e recomendações executam em estação comercial com até 32 GB de
  RAM e GPU de 16 GB — sem dependência de infraestrutura externa em tempo de operação.
