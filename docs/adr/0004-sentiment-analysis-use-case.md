# ADR 0004 - Migração Da Análise De Sentimento Para Use Case

## Status

Aceita

## Contexto

O projeto já possui a camada `application`, os casos de uso `AskQuestionUseCase` e
`ActionPlanUseCase`, além do componente `SemanticRetriever`. Essa arquitetura vem sendo migrada de
forma incremental, preservando o comportamento funcional existente.

O fluxo de Análise de Sentimento ainda estava coordenado diretamente na interface Streamlit. Esse
fluxo utilizava recuperação semântica, geração de relatório de sentimentos organizacionais e
persistência opcional do resultado no histórico.

## Problema

A UI ainda conhecia detalhes de orquestração da Análise de Sentimento:

- consulta semântica usada para recuperar fontes;
- limite de fontes;
- chamada ao gerador de relatório;
- tratamento de erros conhecidos;
- persistência opcional;
- decisão sobre manter o relatório quando a persistência falha.

Isso mantinha acoplamento entre Streamlit e o fluxo de aplicação, reduzia testabilidade isolada e
mantinha lógica de orquestração fora da camada `application`.

## Decisão

Foi criado o `SentimentAnalysisUseCase` em
`src/synapse_ai/application/analysis/sentiment_analysis.py`.

O caso de uso segue o padrão já estabelecido:

- `SentimentAnalysisCommand`;
- `SentimentAnalysisOutput`;
- `UseCaseResult`;
- `ResultSeverity`;
- injeção de dependências por construtor;
- reutilização do `SemanticRetriever`.

## Fluxo Antes

```text
UI Streamlit
↓
consulta fixa de sentimento
↓
_retrieve_sources(...)
↓
generate_sentiment_report(...)
↓
save_sentiment_report_result(...), se solicitado
↓
renderização do relatório e mensagens
```

## Fluxo Depois

```text
UI Streamlit
↓
SentimentAnalysisCommand
↓
SentimentAnalysisUseCase.execute(...)
↓
SemanticRetriever.retrieve(...)
↓
SentimentReportGenerator(...)
↓
SentimentReportSaver(...), se solicitado
↓
UseCaseResult
↓
renderização do relatório e mensagens pela UI
```

## Consequências Positivas

- Redução de responsabilidade da UI.
- Análise de Sentimento passa a seguir o mesmo padrão dos fluxos já migrados.
- Recuperação semântica permanece centralizada no `SemanticRetriever`.
- O fluxo fica testável sem Streamlit, OpenAI ou Supabase reais.
- A persistência opcional continua preservando o relatório gerado em caso de falha.
- A camada `application` ganha mais um caso de uso coeso e tipado.

## Consequências Negativas

- Adição de mais um arquivo de caso de uso.
- A página de análise ainda mantém outros fluxos a serem migrados em fases futuras.
- A migração incremental mantém wrappers temporários na UI até que todas as fases sejam concluídas.

## Alternativas Descartadas

### Manter o fluxo na UI

Foi descartado porque manteria a orquestração de aplicação acoplada ao Streamlit.

### Duplicar a recuperação semântica no novo use case

Foi descartado porque o `SemanticRetriever` já encapsula embeddings, busca vetorial, recuperação de
chunks e construção de `SourceSnippet`.

### Criar um pipeline genérico para todas as análises

Foi descartado por ser uma abstração prematura nesta fase. O escopo era migrar exclusivamente o
fluxo existente de Análise de Sentimento.

### Migrar outros fluxos de análise junto

Foi descartado por estar fora do escopo da Fase 04. Comparação documental, padrões históricos,
alertas, inteligência e multiagente devem permanecer para fases futuras.

## Preservação De Compatibilidade

A migração preserva:

- mesma consulta semântica;
- mesmo limite de fontes;
- mesmo modelo de geração recebido por configuração;
- mesmos serviços de geração e persistência;
- mesmas mensagens de sucesso, alerta, informação e erro;
- mesmo formato de saída renderizado pela UI;
- mesmo comportamento quando a persistência falha.

## Relação Com SemanticRetriever

Como o fluxo real de Análise de Sentimento utiliza recuperação semântica, o novo caso de uso passa
a depender exclusivamente do `SemanticRetriever` para recuperar fontes. O use case não conhece
detalhes de embeddings, busca vetorial, chunks ou construção de `SourceSnippet`.

## Escopo Restrito

Esta decisão implementa apenas a migração do fluxo de Análise de Sentimento para
`SentimentAnalysisUseCase`. Nenhum outro caso de uso foi migrado nesta fase.

