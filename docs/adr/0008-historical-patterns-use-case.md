# ADR 0008 - Migração Dos Padrões Históricos Para Use Case

## Status

Aceita

## Contexto

O projeto já possui a camada `application`, múltiplos casos de uso migrados e o
`SemanticRetriever`. O fluxo de Padrões Históricos ainda estava coordenado diretamente na interface
Streamlit.

Esse fluxo combina duas origens de dados:

- análises recentes persistidas no histórico do usuário;
- fontes atuais recuperadas semanticamente a partir dos documentos selecionados.

## Problema

A UI ainda concentrava responsabilidades de orquestração:

- carregamento do histórico recente;
- definição da consulta semântica;
- limite de registros históricos;
- limite de fontes atuais;
- chamada ao gerador de padrões históricos;
- tratamento de erros conhecidos;
- persistência opcional;
- preservação do relatório quando a persistência falha.

Isso mantinha acoplamento entre Streamlit e o fluxo de aplicação, reduzia testabilidade isolada e
mantinha lógica de orquestração fora da camada `application`.

## Decisão

Foi criado o `HistoricalPatternsUseCase` em
`src/synapse_ai/application/analysis/historical_patterns.py`.

O novo caso de uso segue o padrão já estabelecido:

- `HistoricalPatternsCommand`;
- `HistoricalPatternsOutput`;
- `UseCaseResult`;
- `ResultSeverity`;
- injeção de dependências por construtor;
- reutilização do `SemanticRetriever`;
- carregador de histórico injetado.

## Fluxo Anterior

```text
UI Streamlit
↓
list_recent_analyses(..., limit=30)
↓
_retrieve_sources(..., limit=12)
↓
generate_historical_pattern_report(...)
↓
save_historical_pattern_report_result(...), se solicitado
↓
renderização do relatório e mensagens
```

## Fluxo Atual

```text
UI Streamlit
↓
HistoricalPatternsCommand
↓
HistoricalPatternsUseCase.execute(...)
↓
HistoricalAnalysisLoader(..., limit=30)
↓
SemanticRetriever.retrieve(..., limit=12)
↓
HistoricalPatternReportGenerator(...)
↓
HistoricalPatternReportSaver(...), se solicitado
↓
UseCaseResult
↓
renderização do relatório e mensagens pela UI
```

## Consequências Positivas

- Redução de responsabilidade da UI.
- Padrões Históricos passam a seguir o padrão dos fluxos já migrados.
- Recuperação semântica permanece centralizada no `SemanticRetriever`.
- Carregamento histórico fica injetado e testável.
- O relatório estruturado permanece representado por `HistoricalPatternReport`.
- A falha de persistência continua preservando o relatório gerado.

## Consequências Negativas

- Adição de mais um arquivo de caso de uso.
- A página de análise ainda mantém Multi-Agent Report para fase futura.
- A migração incremental mantém wrappers temporários na UI.

## Alternativas Descartadas

### Manter o fluxo na UI

Foi descartado porque manteria a orquestração de aplicação acoplada ao Streamlit.

### Criar HistoricalAnalysisEngine ou TrendEngine

Foi descartado por ser abstração prematura. A fase migra exclusivamente o fluxo existente de
Padrões Históricos.

### Criar um repositório genérico de histórico

Foi descartado porque já existe uma função concreta de leitura de análises recentes. O caso de uso
recebe apenas essa dependência por contrato pequeno e específico.

### Migrar Multi-Agent Report junto

Foi descartado por estar fora do escopo restrito da Fase 08.

## Compatibilidade

A migração preserva:

- mesma consulta semântica;
- mesmo limite de fontes atuais;
- mesmo limite de análises históricas;
- mesma ausência de janela temporal explícita;
- mesma ordem retornada pelo repositório de histórico;
- mesmo modelo de geração recebido por configuração;
- mesmo serviço de geração;
- mesmo serviço de persistência;
- mesmas mensagens de informação, erro, sucesso e aviso;
- mesmo formato de saída;
- mesmo comportamento quando a persistência falha.

## Origem Dos Dados Históricos

Os dados históricos vêm de `list_recent_analyses`, com limite fixo de 30 registros. Essa função
consulta análises persistidas do usuário e já encapsula o acesso ao banco.

## Relação Com SemanticRetriever

O fluxo utiliza recuperação semântica para fontes atuais dos documentos selecionados. Por isso, o
`HistoricalPatternsUseCase` usa exclusivamente o `SemanticRetriever` para essa parte e não conhece
detalhes de embeddings, busca vetorial, chunks ou construção de `SourceSnippet`.

## Flag De Histórico

A flag existente na UI é a opção de salvar o relatório no histórico. Ela não ativa nem desativa o
uso do histórico como entrada da geração. O use case preserva esse comportamento.

## Intervalo Temporal, Filtros E Limites

Não há intervalo temporal explícito no fluxo atual. Os filtros preservados são usuário e documentos
selecionados. Os limites preservados são 30 análises recentes e 12 fontes atuais.

## Ordenação Cronológica

O caso de uso preserva a ordem retornada por `list_recent_analyses`; não adiciona nova ordenação.

## Ausência De Histórico E Ausência De Padrões

A ausência ou insuficiência de histórico é tratada pelo gerador como `PatternGenerationError` com a
mensagem existente. Ausência de fontes atuais é tratada como informação antes da geração. Ausência
de padrões claros também permanece como `PatternGenerationError`.

## Falhas Parciais

O fluxo não possui tolerância parcial além da persistência opcional. Se a geração for concluída e
a persistência falhar, o relatório é preservado e a UI exibe o aviso existente.

## Escopo Restrito

Esta decisão implementa apenas a migração dos Padrões Históricos para `HistoricalPatternsUseCase`.
Nenhum outro fluxo foi migrado nesta fase.

