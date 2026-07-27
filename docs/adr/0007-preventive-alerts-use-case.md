# ADR 0007 - Migração Dos Alertas Preventivos Para Use Case

## Status

Aceita

## Contexto

O projeto já possui a camada `application`, vários fluxos de análise migrados e o componente
`SemanticRetriever`. O fluxo de Alertas Preventivos ainda estava coordenado diretamente na
interface Streamlit, embora usasse serviços especializados para gerar e persistir o relatório.

O resultado atual é um `PreventiveAlertReport`, composto por:

- síntese executiva;
- lista de alertas preventivos;
- severidades;
- status sugerido;
- gatilhos;
- evidências;
- impactos;
- recomendações;
- responsáveis e prazos sugeridos;
- fontes.

## Problema

A UI ainda concentrava responsabilidades de orquestração dos Alertas Preventivos:

- definição da consulta semântica;
- limite de fontes recuperadas;
- chamada ao gerador de alertas;
- tratamento de erros conhecidos;
- persistência opcional;
- preservação do relatório quando a persistência falha.

Isso mantinha acoplamento entre Streamlit e o fluxo de aplicação, reduzia testabilidade isolada e
mantinha lógica de orquestração fora da camada `application`.

## Decisão

Foi criado o `PreventiveAlertsUseCase` em
`src/synapse_ai/application/analysis/preventive_alerts.py`.

O novo caso de uso segue o padrão já estabelecido:

- `PreventiveAlertsCommand`;
- `PreventiveAlertsOutput`;
- `UseCaseResult`;
- `ResultSeverity`;
- injeção de dependências por construtor;
- reutilização do `SemanticRetriever`.

## Fluxo Anterior

```text
UI Streamlit
↓
consulta fixa de alertas preventivos
↓
_retrieve_sources(...)
↓
generate_preventive_alert_report(...)
↓
save_preventive_alert_report_result(...), se solicitado
↓
renderização do relatório e mensagens
```

## Fluxo Atual

```text
UI Streamlit
↓
PreventiveAlertsCommand
↓
PreventiveAlertsUseCase.execute(...)
↓
SemanticRetriever.retrieve(...)
↓
PreventiveAlertReportGenerator(...)
↓
PreventiveAlertReportSaver(...), se solicitado
↓
UseCaseResult
↓
renderização do relatório e mensagens pela UI
```

## Consequências Positivas

- Redução de responsabilidade da UI.
- Alertas Preventivos passam a seguir o padrão dos fluxos já migrados.
- Recuperação semântica permanece centralizada no `SemanticRetriever`.
- O fluxo fica testável sem Streamlit, OpenAI ou Supabase reais.
- O relatório estruturado permanece representado por `PreventiveAlertReport`.
- A falha de persistência continua preservando o relatório gerado.

## Consequências Negativas

- Adição de mais um arquivo de caso de uso.
- A página de análise ainda mantém fluxos a serem migrados em fases futuras.
- A migração incremental mantém wrappers temporários na UI.

## Alternativas Descartadas

### Manter o fluxo na UI

Foi descartado porque manteria a orquestração de aplicação acoplada ao Streamlit.

### Criar um AlertEngine ou AlertPipeline

Foi descartado por ser abstração prematura. A fase migra exclusivamente o fluxo existente de
Alertas Preventivos.

### Duplicar a recuperação semântica no novo use case

Foi descartado porque o fluxo atual usa recuperação semântica e o `SemanticRetriever` já encapsula
embeddings, busca vetorial, chunks e construção de `SourceSnippet`.

### Migrar Padrões Históricos ou Multi-Agent Report junto

Foi descartado por estar fora do escopo restrito da Fase 07.

## Compatibilidade

A migração preserva:

- mesma consulta semântica;
- mesmo limite de fontes;
- mesmo modelo de geração recebido por configuração;
- mesmo serviço de geração;
- mesmo serviço de persistência;
- mesmas mensagens de informação, erro, sucesso e aviso;
- mesmas severidades de mensagens;
- mesmo formato de saída;
- mesmo comportamento quando a persistência falha.

## Relação Com SemanticRetriever

Como o fluxo real utiliza recuperação semântica, o `PreventiveAlertsUseCase` depende
exclusivamente do `SemanticRetriever` para obter fontes. O caso de uso não conhece detalhes de
embeddings, busca vetorial, chunks ou construção de `SourceSnippet`.

## Comportamento Quando Não Existem Alertas

O comportamento atual não considera ausência de alertas claros como resultado válido. O serviço
lança `AlertGenerationError` com a mensagem existente, e o novo caso de uso preserva isso como
`UseCaseResult.fail(...)` com severidade de erro.

## Escopo Da Fase

Esta decisão implementa apenas a migração dos Alertas Preventivos para `PreventiveAlertsUseCase`.
Nenhum outro fluxo foi migrado nesta fase.

