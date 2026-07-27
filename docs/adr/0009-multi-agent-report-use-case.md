# ADR 0009 - Migração Do Multi-Agent Report Para Use Case

## Status

Aceita

## Contexto

O projeto já possui uma camada `application` consolidada por casos de uso incrementais e pelo
`SemanticRetriever`. A inspeção arquitetural do fluxo de Multi-Agent Report mostrou que ele é uma
orquestração multiagente explícita, composta por cinco agentes especializados e um orquestrador
final.

O serviço `generate_multi_agent_report(...)` já encapsula a execução interna dos agentes, a ordem
fixa definida em `SPECIALIZED_AGENTS`, a construção do resumo histórico, a validação dos achados, a
chamada do orquestrador e a montagem do `MultiAgentReport`.

## Problema

A UI ainda concentrava a orquestração externa do fluxo:

- carregamento de histórico recente com limite 30;
- definição da consulta semântica fixa;
- recuperação semântica com limite 14;
- tratamento de ausência de fontes;
- chamada direta ao gerador multiagente;
- tratamento de erros conhecidos;
- persistência opcional;
- preservação do relatório quando somente a persistência falhava.

Isso mantinha acoplamento entre Streamlit, Supabase, OpenAI, recuperação semântica e persistência.

## Decisão

Foi criado o `MultiAgentReportUseCase` em
`src/synapse_ai/application/analysis/multi_agent_report.py`.

O novo caso de uso contém:

- `MultiAgentReportCommand`;
- `MultiAgentReportOutput`;
- `MULTI_AGENT_REPORT_QUERY`;
- `MULTI_AGENT_REPORT_SOURCE_LIMIT`;
- `MULTI_AGENT_HISTORY_LIMIT`;
- dependências injetadas por construtor.

O caso de uso coordena apenas o fluxo externo:

```text
HistoricalAnalysisLoader(..., limit=30)
↓
SemanticRetriever.retrieve(..., limit=14)
↓
MultiAgentReportGenerator(...)
↓
MultiAgentReportSaver(...), se solicitado
↓
UseCaseResult[MultiAgentReportOutput]
```

## Classificação Arquitetural

O fluxo foi classificado como **orquestração multiagente explícita**.

Essa classificação foi preservada sem introduzir engine genérica, pipeline, supervisor dinâmico ou
configuração de agentes. A orquestração interna continua no serviço existente.

## Fluxo Anterior

```text
UI Streamlit
↓
list_recent_analyses(..., limit=30)
↓
_retrieve_sources(..., query fixa, limit=14)
↓
generate_multi_agent_report(...)
↓
save_multi_agent_report_result(...), se solicitado
↓
renderização do relatório e mensagens
```

## Fluxo Atual

```text
UI Streamlit
↓
MultiAgentReportCommand
↓
MultiAgentReportUseCase.execute(...)
↓
list_recent_analyses(..., limit=30)
↓
SemanticRetriever.retrieve(..., query fixa, limit=14)
↓
generate_multi_agent_report(...)
↓
save_multi_agent_report_result(...), se solicitado
↓
UseCaseResult
↓
renderização do relatório e mensagens
```

## Responsabilidades Do Use Case

- Validar o comando.
- Carregar histórico recente com limite 30.
- Recuperar fontes atuais com `SemanticRetriever`.
- Preservar a consulta semântica fixa.
- Preservar o limite semântico 14.
- Chamar o gerador multiagente existente.
- Persistir opcionalmente.
- Preservar o relatório se apenas a persistência falhar.
- Converter erros conhecidos para `UseCaseResult`.

## Responsabilidades Preservadas Em `agent_service.py`

- Gerar `history_digest`.
- Executar os cinco agentes especializados.
- Preservar a ordem de `SPECIALIZED_AGENTS`.
- Validar achados individuais.
- Interromper quando todos os agentes retornarem sem achados.
- Chamar o orquestrador final.
- Interpretar respostas JSON.
- Montar `AgentOutput`, `AgentFinding` e `MultiAgentReport`.
- Exportar Markdown, CSV e XLSX.

## Por Que Não Desmontar O Serviço

Desmontar `agent_service.py` nesta fase aumentaria o risco de alterar:

- prompts;
- ordem dos agentes;
- contexto enviado a cada agente;
- comportamento de falha;
- formato dos outputs;
- contrato de exportação e persistência.

A menor mudança arquitetural segura é mover a orquestração externa para a camada `application` e
manter a orquestração interna estável.

## Por Que Não Criar Engine Ou Pipeline

O fluxo atual não possui agentes configuráveis, paralelismo, retries, votação, consenso iterativo,
DAG, supervisor dinâmico ou tolerância parcial. Criar uma engine genérica seria abstração prematura
e ampliaria o escopo da fase.

## Uso Do SemanticRetriever

A antiga recuperação semântica privada da UI foi substituída pelo `SemanticRetriever`, preservando:

- usuário;
- documentos selecionados;
- modelo de embedding;
- construção de `SourceSnippet`;
- ordem retornada pela busca vetorial;
- tratamento dos erros conhecidos.

## Query E Limites

A consulta fixa preservada é:

```text
decisões, riscos, inconsistências, sentimentos, governança, responsáveis, prazos, evidências, recomendações, padrões históricos e lacunas de auditoria
```

O limite semântico preservado é `14`.

O limite de histórico preservado é `30`.

## Execução Sequencial E Ordem Fixa

O Use Case não conhece `SPECIALIZED_AGENTS`. A execução sequencial e a ordem fixa permanecem
exatamente no serviço multiagente.

## Ausência De Falha Parcial

O fluxo continua sem tolerância parcial. Falha de agente, resposta inválida, ausência total de
achados ou falha do orquestrador continuam encerrando a geração como erro.

## Comportamento Sem Fontes

Ausência de fontes é tratada antes do gerador e retorna informação com a mensagem existente:

```text
Nenhum trecho relevante foi encontrado. Atualize a base semântica antes de executar os agentes.
```

## Comportamento Sem Achados

Quando os agentes não encontram achados claros, o serviço mantém o erro existente:

```text
Os agentes não encontraram achados claros neste escopo.
```

## Persistência Opcional

A persistência continua controlada exclusivamente por `save_to_history`.

O Use Case preserva a chamada concreta de `save_multi_agent_report_result(...)` por injeção de
dependência, sem alterar metadata, título, pergunta fixa, status, fontes ou Markdown persistido.

## Falha De Persistência

Quando a geração termina com sucesso e somente a persistência falha, o relatório é preservado e o
aviso existente é retornado:

```text
Não foi possível salvar a orquestração multiagente.
```

## Compatibilidade

A migração preserva:

- mesmo ponto de entrada funcional;
- mesma flag de salvamento;
- mesmos documentos selecionados;
- mesmo modelo de embedding;
- mesmo modelo de geração;
- mesmos prompts;
- mesmos agentes;
- mesma ordem;
- mesmo `MultiAgentReport`;
- mesmas exportações;
- mesma persistência;
- mesmas mensagens e severidades.

## Consequências Positivas

- Redução de responsabilidade da UI.
- Recuperação semântica centralizada no `SemanticRetriever`.
- Fluxo externo testável de forma unitária.
- Melhor preparação para migrar a interface no futuro.
- Menor acoplamento entre Streamlit e serviços de aplicação.

## Consequências Negativas

- Mais um arquivo na camada `application`.
- A orquestração interna dos agentes permanece em um serviço concreto.
- O fluxo ainda não oferece tolerância parcial, paralelismo ou telemetria fina, por preservação de
  comportamento.

## Alternativas Descartadas

### Manter O Fluxo Na UI

Descartado porque manteria a orquestração externa acoplada à interface Streamlit.

### Criar MultiAgentEngine Ou WorkflowEngine

Descartado porque o comportamento atual não justifica uma engine genérica.

### Desmontar `agent_service.py`

Descartado por risco elevado de alterar prompts, ordem, parsing e contratos.

### Paralelizar Agentes

Descartado porque mudaria o modelo de execução atual.

### Implementar Tolerância Parcial

Descartado porque mudaria o comportamento de falha atual.

## Escopo Restrito Da Fase

Esta decisão implementa apenas a migração da orquestração externa do Multi-Agent Report para
`MultiAgentReportUseCase`. Nenhum outro fluxo foi migrado nesta fase.
