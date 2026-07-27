# ADR 0003 - Migração Do Plano De Ação Para Use Case

## Status

Aceita

## Contexto

O projeto já possui uma camada `application`, o `AskQuestionUseCase` e o `SemanticRetriever`.
Esses componentes estabeleceram um padrão para mover orquestrações de aplicação para fora da UI
sem alterar comportamento, prompts, modelos, banco de dados ou contratos públicos.

O fluxo de geração de plano de ação ainda estava coordenado diretamente na interface Streamlit.
Esse fluxo fazia:

- definição da consulta semântica usada para recuperar evidências;
- recuperação de fontes;
- geração do plano de ação;
- persistência opcional;
- tratamento de erros;
- renderização do resultado.

## Problema

A UI ainda concentrava parte da orquestração de aplicação no fluxo de plano de ação.

Isso mantinha alguns riscos:

- acoplamento entre Streamlit e regras de orquestração;
- repetição do padrão de recuperação semântica fora da camada `application`;
- menor testabilidade do fluxo de plano de ação;
- crescimento progressivo da página de análise;
- dificuldade futura para expor o mesmo fluxo em outra interface.

## Decisão

Foi criado o `ActionPlanUseCase` em `application/analysis/action_plan.py`.

O novo caso de uso segue o mesmo padrão arquitetural do `AskQuestionUseCase`:

- `ActionPlanCommand`;
- `ActionPlanOutput`;
- `UseCaseResult`;
- `ResultSeverity`;
- injeção de dependências por construtor;
- reutilização obrigatória do `SemanticRetriever`.

O `ActionPlanUseCase` coordena apenas três passos de alto nível:

```text
SemanticRetriever.retrieve()
↓
ActionPlanGenerator()
↓
ActionPlanSaver()
```

A UI permanece responsável apenas por chamar `execute(...)` e renderizar o resultado.

## Consequências

### Positivas

- Redução de responsabilidade da UI.
- Reutilização do `SemanticRetriever`.
- Melhor testabilidade do fluxo de plano de ação.
- Menor acoplamento entre Streamlit e orquestração de aplicação.
- Maior consistência entre os fluxos já migrados para a camada `application`.
- Preservação integral do comportamento atual.

### Negativas

- Adição de mais um arquivo de caso de uso.
- A página de análise ainda mantém outros fluxos a serem migrados em fases futuras.
- Existe uma transição gradual em que a UI ainda possui wrappers temporários.

## Alternativas Descartadas

### Manter o fluxo de plano de ação na UI

Foi descartado porque manteria a orquestração fora da camada `application` e reduziria a
consistência arquitetural com o fluxo de perguntas.

### Criar uma abstração genérica para todos os artefatos analíticos

Foi descartado por antecipar fases futuras. Nesta etapa, o objetivo era migrar somente o plano de
ação, sem criar generalizações prematuras.

### Duplicar a recuperação semântica dentro do novo use case

Foi descartado porque o `SemanticRetriever` já encapsula esse fluxo e deve ser reutilizado por
qualquer caso de uso que precise recuperar fontes.

### Migrar todos os fluxos restantes de análise

Foi descartado por estar fora do escopo da Fase 03. A migração deve ocorrer de forma incremental
para reduzir risco e preservar estabilidade.

