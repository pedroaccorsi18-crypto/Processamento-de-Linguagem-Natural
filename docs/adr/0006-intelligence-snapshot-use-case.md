# ADR 0006 - Migração Da Inteligência Organizacional Para Use Case

## Status

Aceita

## Contexto

O projeto já possui a camada `application`, múltiplos casos de uso migrados e o componente
`SemanticRetriever`. O fluxo de Inteligência Organizacional ainda estava coordenado diretamente na
interface Streamlit, embora já utilizasse serviços especializados para geração e persistência do
snapshot.

O resultado atual é composto por:

- síntese executiva;
- achados estruturados;
- fontes recuperadas.

## Problema

A UI ainda concentrava responsabilidades de orquestração da Inteligência Organizacional:

- definição da consulta semântica;
- limite de fontes recuperadas;
- chamada ao gerador de inteligência;
- tratamento de erros conhecidos;
- persistência opcional;
- preservação do snapshot quando a persistência falha.

Isso mantinha acoplamento entre Streamlit e o fluxo de aplicação, reduzia testabilidade isolada e
mantinha lógica de orquestração fora da camada `application`.

## Decisão

Foi criado o `IntelligenceSnapshotUseCase` em
`src/synapse_ai/application/analysis/intelligence_snapshot.py`.

O novo caso de uso segue o padrão já estabelecido:

- `IntelligenceSnapshotCommand`;
- `IntelligenceSnapshotOutput`;
- `UseCaseResult`;
- `ResultSeverity`;
- injeção de dependências por construtor;
- reutilização do `SemanticRetriever`.

## Fluxo Anterior

```text
UI Streamlit
↓
consulta fixa de inteligência organizacional
↓
_retrieve_sources(...)
↓
generate_intelligence_snapshot(...)
↓
save_intelligence_snapshot_result(...), se solicitado
↓
renderização do snapshot e mensagens
```

## Fluxo Atual

```text
UI Streamlit
↓
IntelligenceSnapshotCommand
↓
IntelligenceSnapshotUseCase.execute(...)
↓
SemanticRetriever.retrieve(...)
↓
IntelligenceSnapshotGenerator(...)
↓
IntelligenceSnapshotSaver(...), se solicitado
↓
UseCaseResult
↓
renderização do snapshot e mensagens pela UI
```

## Consequências Positivas

- Redução de responsabilidade da UI.
- Inteligência Organizacional passa a seguir o padrão dos fluxos já migrados.
- Recuperação semântica permanece centralizada no `SemanticRetriever`.
- O fluxo fica testável sem Streamlit, OpenAI ou Supabase reais.
- O resultado composto permanece tipado como `IntelligenceSnapshot`.
- A falha de persistência continua preservando o snapshot gerado.

## Consequências Negativas

- Adição de mais um arquivo de caso de uso.
- A página de análise ainda mantém fluxos a serem migrados em fases futuras.
- A migração incremental mantém wrappers temporários na UI.

## Alternativas Descartadas

### Manter o fluxo na UI

Foi descartado porque manteria a orquestração de aplicação acoplada ao Streamlit.

### Duplicar a recuperação semântica no novo use case

Foi descartado porque o fluxo atual usa recuperação semântica e o `SemanticRetriever` já encapsula
embeddings, busca vetorial, chunks e construção de `SourceSnippet`.

### Criar um pipeline genérico de análises

Foi descartado por ser abstração prematura. A fase migra exclusivamente Inteligência
Organizacional.

### Migrar alertas, padrões históricos ou multiagente junto

Foi descartado por estar fora do escopo restrito da Fase 06.

## Compatibilidade

A migração preserva:

- mesma consulta semântica;
- mesmo limite de fontes;
- mesmo modelo de geração recebido por configuração;
- mesmo serviço de geração;
- mesmo serviço de persistência;
- mesmas mensagens de informação, erro, sucesso e aviso;
- mesmo formato composto de saída;
- mesmo comportamento quando a persistência falha.

## Relação Com SemanticRetriever

Como o fluxo real utiliza recuperação semântica, o `IntelligenceSnapshotUseCase` depende
exclusivamente do `SemanticRetriever` para obter fontes. O caso de uso não conhece detalhes de
embeddings, busca vetorial, chunks ou construção de `SourceSnippet`.

## Tratamento De Resultado Composto

O snapshot continua sendo representado pelo modelo existente `IntelligenceSnapshot`, sem conversão
para nova estrutura funcional. A UI segue renderizando síntese executiva, achados e fontes com o
mesmo formato anterior.

## Tratamento De Falhas Parciais

O fluxo não possui múltiplas etapas independentes com tolerância parcial. A única falha parcial
preservada é a falha de persistência após geração bem-sucedida: nesse caso, o snapshot continua
sendo retornado e a UI exibe o aviso correspondente.

## Escopo Restrito

Esta decisão implementa apenas a migração do fluxo de Inteligência Organizacional para
`IntelligenceSnapshotUseCase`. Nenhum outro caso de uso foi migrado nesta fase.

