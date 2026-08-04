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
      ┌──────────────────────┐
      │  API (FastAPI)       │
      └──────────┬───────────┘
                 │
    ┌────────────┼─────────────┐
    ▼            ▼             ▼
 similaridade  classificador  RAG documental
 (k-NN)        (defeito)      (embeddings + LLM local)
    │            │             │
    └────────────┼─────────────┘
                 ▼
       resposta prescritiva
   (defeito, nº de ocorrências, frequência,
    distribuição temporal, ação recomendada,
    fontes citadas)  ── ou ──  "defeito sem
    documentação: cadastre um documento"
                 │
                 ▼
        Interface (Streamlit)
     chat · dashboard · upload de docs
```

Detalhamento em [docs/arquitetura.md](docs/arquitetura.md), incluindo a proposta de
implantação em ambiente industrial.

## Decisões técnicas

Cada decisão relevante é registrada no formato contexto → alternativas → escolha →
justificativa → consequências aceitas. Resumo das principais:

| Decisão | Escolha | Porquê |
| --- | --- | --- |
| LLM | Qwen2.5 7B Instruct, local via Ollama | ~4,7 GB quantizado: cabe na GPU de 16 GB e opera offline — o dado industrial não sai da planta |
| Interface | FastAPI + Streamlit | O consumidor natural em ambiente industrial é o supervisório, não um navegador: a API é o contrato de integração |
| Identificação do defeito | Rótulo do operador, normalizado deterministicamente | O `fault` vem no JSON de entrada; um classificador sobre as features rende 11% fora de sessão, abaixo do baseline |
| Busca por similaridade | k-NN global, com o defeito de cada vizinho exibido | Responde ao que o enunciado pede e é explicável: a resposta *é* a lista de vizinhos |
| Recuperação documental | Fatiamento por seção numerada, `multilingual-e5-large`, ChromaDB | Procedimentos passo a passo chegam inteiros e a citação de fonte fica verificável |
| Anti-alucinação | Duas barreiras: mapa defeito→documento e limiar calibrado | A primeira não envolve modelo algum — é consulta a dicionário, impossível de furar |

## Dados

O conjunto completo (`banner.csv`, 166.796 eventos, 32 MB) é distribuído pelo Google Drive
indicado no enunciado. O repositório versiona uma **amostra estratificada por rótulo bruto**
em `data/amostra_banner.csv` (5.120 eventos, os 151 rótulos representados), suficiente para
executar os testes e explorar a solução sem download.

```bash
python scripts/gerar_amostra.py    # regenera a amostra a partir do arquivo completo
```

O arquivo `banner.xlsx` distribuído junto **não deve ser usado**: seus valores decimais estão
corrompidos de forma intermitente (`0.0427` gravado como `427.0`, misturando texto e número
na mesma coluna). O CSV é a única fonte confiável.

## Estrutura do repositório

```
data/          amostra estratificada dos eventos
docs/          arquitetura, dados originais e documentação técnica
notebooks/     análise exploratória e validação dos modelos
scripts/       utilitários de preparação
src/           código-fonte da solução
  ingestion/   carga dos eventos e normalização canônica dos rótulos
  features/    engenharia de atributos
  similarity/  busca por ocorrências semelhantes
  rag/         indexação documental, recuperação e geração
  api/         camada FastAPI
app/           interface Streamlit
tests/         testes automatizados
```

## Como executar

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
pytest                            # suíte de testes
```

Instruções completas de execução da solução em `docs/execucao.md` (em construção).

## Restrições atendidas

- Implementação integralmente em Python.
- Inferência, consultas e recomendações executam em estação comercial com até 32 GB de
  RAM e GPU de 16 GB — sem dependência de infraestrutura externa em tempo de operação.
