# Camada Application

A camada `application` concentra os casos de uso do Synapse AI. Ela fica entre a interface
Streamlit e os serviços de domínio, coordenando fluxos de aplicação sem alterar regras de
negócio, prompts, banco de dados ou modelos.

## Responsabilidade

Esta camada deve:

- receber comandos vindos da UI;
- coordenar serviços e repositórios já existentes;
- tratar erros esperados de aplicação;
- retornar resultados estruturados para a interface;
- manter a UI focada em entrada, validação simples e renderização.

Esta camada não deve:

- criar clientes externos internamente;
- acessar secrets diretamente;
- definir prompts;
- renderizar componentes Streamlit;
- alterar contratos de banco;
- conter regras de negócio que já pertencem aos serviços.

## Fluxo

O fluxo esperado é:

```text
UI
↓
Command
↓
Use Case
↓
Services / Repositories / Clients injetados
↓
UseCaseResult
↓
UI renderiza o resultado
```

Na Fase 01, o padrão completo foi aplicado ao `AskQuestionUseCase`, responsável por:

- recuperar fontes semanticamente relevantes;
- gerar a resposta RAG;
- persistir a análise quando solicitado;
- tratar erros conhecidos;
- devolver uma resposta estruturada para a UI.

Na Fase 03, o mesmo padrão foi aplicado ao `ActionPlanUseCase`, responsável por:

- reutilizar o `SemanticRetriever` para recuperar fontes;
- gerar o plano de ação a partir dos trechos recuperados;
- persistir o plano quando solicitado;
- tratar erros conhecidos;
- devolver o plano estruturado para renderização pela UI.

Na Fase 04, o fluxo de Análise de Sentimento foi migrado para o
`SentimentAnalysisUseCase`, responsável por:

- reutilizar o `SemanticRetriever` para recuperar fontes sobre sentimento organizacional;
- gerar o relatório de sentimentos a partir das fontes recuperadas;
- persistir o relatório quando solicitado;
- preservar o relatório gerado mesmo quando a persistência falhar;
- devolver o resultado estruturado para renderização pela UI.

Na Fase 05, o fluxo de Comparação Documental foi migrado para o
`DocumentComparisonUseCase`, responsável por:

- validar o escopo mínimo de documentos selecionados;
- reutilizar o `SemanticRetriever` para recuperar fontes comparativas;
- gerar o relatório de divergências documentais;
- persistir o relatório quando solicitado;
- preservar o relatório gerado mesmo quando a persistência falhar;
- devolver o resultado estruturado para renderização pela UI.

Na Fase 06, o fluxo de Inteligência Organizacional foi migrado para o
`IntelligenceSnapshotUseCase`, responsável por:

- reutilizar o `SemanticRetriever` para recuperar fontes sobre decisões, riscos e pendências;
- gerar o `IntelligenceSnapshot` composto por síntese executiva, achados e fontes;
- persistir o snapshot quando solicitado;
- preservar o snapshot gerado mesmo quando a persistência falhar;
- devolver o resultado estruturado para renderização pela UI.

Na Fase 07, o fluxo de Alertas Preventivos foi migrado para o
`PreventiveAlertsUseCase`, responsável por:

- reutilizar o `SemanticRetriever` para recuperar fontes sobre riscos e sinais preventivos;
- gerar o `PreventiveAlertReport` com síntese executiva, alertas, severidades e recomendações;
- persistir o relatório quando solicitado;
- preservar o relatório gerado mesmo quando a persistência falhar;
- preservar o comportamento atual em que ausência de alertas claros é erro conhecido de geração;
- devolver o resultado estruturado para renderização pela UI.

Na Fase 08, o fluxo de Padrões Históricos foi migrado para o
`HistoricalPatternsUseCase`, responsável por:

- carregar análises recentes persistidas com limite fixo de 30 registros;
- reutilizar o `SemanticRetriever` para recuperar fontes atuais com limite fixo de 12 trechos;
- preservar a ordem retornada pelo repositório de histórico;
- gerar o `HistoricalPatternReport` combinando fontes atuais e histórico salvo;
- persistir o relatório quando solicitado pela flag de histórico da UI;
- preservar o relatório gerado mesmo quando a persistência falhar;
- preservar o comportamento atual em que histórico insuficiente ou ausência de padrões é erro
  conhecido de geração.

Na Fase 09, o fluxo de Orquestração Multiagente foi migrado para o
`MultiAgentReportUseCase`, responsável por:

- validar o comando sem alterar as validações simples já feitas pela UI;
- carregar análises recentes persistidas com limite fixo de 30 registros;
- reutilizar o `SemanticRetriever` para recuperar fontes atuais com a consulta fixa multiagente;
- preservar o limite semântico fixo de 14 trechos;
- chamar o gerador multiagente existente sem conhecer agentes individuais;
- persistir o relatório quando solicitado pela flag de histórico da UI;
- preservar o `MultiAgentReport` gerado mesmo quando a persistência falhar;
- preservar falhas totais para ausência de fontes, falha de agente, ausência de achados,
  falha do orquestrador e respostas inválidas.

Na Fase 11, os dois fluxos residuais com orquestração de IA foram migrados para Use Cases
dedicados:

- `PrepareSemanticBaseUseCase`, responsável por preparar a base semântica de documentos;
- `IntelligentExecutiveReportUseCase`, responsável por gerar o relatório executivo inteligente
  do Dashboard.

O `PrepareSemanticBaseUseCase` coordena:

- divisão do texto extraído em chunks;
- geração de embeddings;
- substituição dos chunks persistidos do documento;
- contagem total de trechos indexados;
- tratamento dos erros conhecidos de embeddings e persistência.

O `IntelligentExecutiveReportUseCase` coordena:

- recuperação de evidências com o `SemanticRetriever`;
- preservação da consulta executiva fixa;
- preservação do limite fixo de 10 fontes;
- geração do `IntelligentExecutiveReport`;
- tratamento de ausência de evidências e erros conhecidos;
- devolução do relatório estruturado para renderização e download pela UI.

O `agent_service.py` permanece responsável por:

- gerar o resumo histórico usado pelos agentes;
- executar os cinco agentes especializados em ordem fixa;
- chamar o orquestrador final;
- validar e transformar respostas JSON em `AgentOutput`, `AgentFinding` e `MultiAgentReport`;
- exportar o relatório em Markdown, CSV e XLSX.

O `MultiAgentReportUseCase` não introduz tolerância parcial, paralelismo, retries, engine de
workflow, configuração dinâmica de agentes ou novas consultas por agente.

## Como Criar Novos Use Cases

1. Crie um arquivo dentro do subpacote do domínio, por exemplo `application/analysis/`.
2. Defina um `Command` imutável com os dados de entrada.
3. Defina um `Output` imutável com o resultado esperado.
4. Crie uma classe com método `execute(command)`.
5. Receba todas as dependências pelo construtor.
6. Retorne sempre `UseCaseResult`.
7. Exporte o novo caso de uso no `__init__.py` do subpacote.

## Dependências

Use cases não devem instanciar dependências diretamente. Clientes, serviços, repositórios e
funções externas devem ser recebidos pelo construtor.

Exemplo:

```text
AskQuestionUseCase(
    semantic_retriever,
    rag_answer_generator,
    analysis_saver,
)

ActionPlanUseCase(
    semantic_retriever,
    action_plan_generator,
    action_plan_saver,
)

SentimentAnalysisUseCase(
    semantic_retriever,
    sentiment_report_generator,
    sentiment_report_saver,
)

DocumentComparisonUseCase(
    semantic_retriever,
    document_comparison_generator,
    document_comparison_saver,
)

IntelligenceSnapshotUseCase(
    semantic_retriever,
    intelligence_snapshot_generator,
    intelligence_snapshot_saver,
)

PreventiveAlertsUseCase(
    semantic_retriever,
    preventive_alert_report_generator,
    preventive_alert_report_saver,
)

HistoricalPatternsUseCase(
    historical_analysis_loader,
    semantic_retriever,
    historical_pattern_report_generator,
    historical_pattern_report_saver,
)

MultiAgentReportUseCase(
    historical_analysis_loader,
    semantic_retriever,
    multi_agent_report_generator,
    multi_agent_report_saver,
)

PrepareSemanticBaseUseCase(
    text_chunker,
    embedding_generator,
    document_chunk_replacer,
)

IntelligentExecutiveReportUseCase(
    semantic_retriever,
    intelligent_executive_report_generator,
)
```

Isso reduz acoplamento, facilita testes e prepara o projeto para evoluir futuramente para
FastAPI, workers assíncronos ou outra interface sem reescrever a lógica de aplicação.

## Composition Roots

A camada `application` não instancia dependências concretas. A montagem dos Use Cases para a UI
Streamlit fica concentrada em builders específicos:

- `src/synapse_ai/ui/analysis_use_cases.py`, para fluxos da página de análises e preparação da base;
- `src/synapse_ai/ui/dashboard_use_cases.py`, para fluxos do Dashboard.

Essa separação mantém a injeção de dependências explícita e evita que a interface conheça detalhes
de chunking, embeddings, busca vetorial, persistência ou geração de relatórios.
