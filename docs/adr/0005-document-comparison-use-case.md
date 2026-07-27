# ADR 0005 - Migração Da Comparação Documental Para Use Case

## Status

Aceita

## Contexto

O projeto já possui a camada `application`, os casos de uso `AskQuestionUseCase`,
`ActionPlanUseCase` e `SentimentAnalysisUseCase`, além do componente `SemanticRetriever`.

O fluxo de Comparação Documental ainda estava coordenado diretamente na interface Streamlit. Esse
fluxo exigia ao menos dois documentos selecionados, recuperava fontes por busca semântica, gerava
um relatório de divergências e persistia opcionalmente o resultado no histórico.

## Problema

A UI ainda concentrava responsabilidades de orquestração da comparação documental:

- validação do número mínimo de documentos;
- definição da consulta semântica de comparação;
- limite de fontes recuperadas;
- chamada ao gerador de comparação;
- tratamento de erros conhecidos;
- persistência opcional;
- preservação do relatório quando a persistência falha.

Isso mantinha acoplamento entre Streamlit e o fluxo de aplicação, dificultava testes isolados e
mantinha lógica de orquestração fora da camada `application`.

## Decisão

Foi criado o `DocumentComparisonUseCase` em
`src/synapse_ai/application/analysis/document_comparison.py`.

O novo caso de uso segue o padrão incremental já estabelecido:

- `DocumentComparisonCommand`;
- `DocumentComparisonOutput`;
- `UseCaseResult`;
- `ResultSeverity`;
- injeção de dependências por construtor;
- reutilização do `SemanticRetriever`.

O fluxo passa a ser:

```text
UI Streamlit
↓
DocumentComparisonCommand
↓
DocumentComparisonUseCase.execute(...)
↓
SemanticRetriever.retrieve(...)
↓
DocumentComparisonGenerator(...)
↓
DocumentComparisonSaver(...), se solicitado
↓
UseCaseResult
↓
renderização pela UI
```

## Consequências

### Positivas

- Redução de responsabilidade da UI.
- Comparação Documental passa a seguir o mesmo padrão dos fluxos já migrados.
- Recuperação semântica permanece centralizada no `SemanticRetriever`.
- Fluxo testável sem Streamlit, OpenAI ou Supabase reais.
- Validação do escopo mínimo fica junto da orquestração do caso de uso.
- Persistência opcional preserva o relatório gerado em caso de falha.

### Negativas

- Adição de mais um arquivo de caso de uso.
- A página de análise ainda possui outros fluxos a serem migrados em fases futuras.
- A migração incremental mantém wrappers temporários na UI.

## Alternativas Descartadas

### Manter o fluxo na UI

Foi descartado porque manteria a orquestração de aplicação acoplada ao Streamlit.

### Duplicar a recuperação semântica no novo use case

Foi descartado porque o fluxo atual usa recuperação semântica e o `SemanticRetriever` já encapsula
embeddings, busca vetorial, chunks e construção de `SourceSnippet`.

### Criar um pipeline genérico para análises documentais

Foi descartado por ser abstração prematura. Esta fase migra exclusivamente Comparação Documental.

### Migrar outros fluxos simultaneamente

Foi descartado por estar fora do escopo da Fase 05. Outros fluxos devem continuar sendo migrados em
fases separadas.

## Compatibilidade Preservada

A migração preserva:

- mesma validação de pelo menos dois documentos;
- mesma consulta semântica;
- mesmo limite de fontes;
- mesmo modelo de geração recebido por configuração;
- mesmo serviço de geração de comparação;
- mesmo serviço de persistência;
- mesmas mensagens de warning, info, error e success;
- mesmo formato de relatório renderizado pela UI;
- mesmo comportamento quando a persistência falha.

