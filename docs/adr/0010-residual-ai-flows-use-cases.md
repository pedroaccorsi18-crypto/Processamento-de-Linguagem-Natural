# ADR 0010 - Migração Dos Fluxos Residuais De IA Para Use Cases

## Status

Aceita

## Contexto

O projeto já possuía uma camada `application` consolidada para os principais fluxos de análise:
perguntas RAG, plano de ação, sentimento, comparação documental, inteligência organizacional,
alertas preventivos, padrões históricos e orquestração multiagente.

Após essas fases, restavam dois fluxos com orquestração relevante fora da camada de aplicação:

- preparação da base semântica na página de análises;
- geração do relatório executivo inteligente no Dashboard.

Esses fluxos não representam novas funcionalidades. Eles já existiam e estavam operacionais.

## Problema

A UI ainda conhecia detalhes de processos de IA e infraestrutura:

- divisão de texto em chunks;
- geração de embeddings;
- substituição de chunks persistidos;
- recuperação semântica para relatório executivo;
- consulta fixa do relatório;
- limite fixo de fontes;
- chamada direta ao gerador de relatório executivo inteligente;
- tratamento de erros esperados desses fluxos.

Isso mantinha acoplamento residual entre Streamlit, serviços de IA, persistência e regras de
orquestração.

## Decisão

Foram criados dois Use Cases dedicados:

- `PrepareSemanticBaseUseCase`, em
  `src/synapse_ai/application/indexing/prepare_semantic_base.py`;
- `IntelligentExecutiveReportUseCase`, em
  `src/synapse_ai/application/dashboard/intelligent_executive_report.py`.

Cada caso de uso possui:

- `Command` imutável;
- `Output` imutável;
- dependências injetadas pelo construtor;
- retorno padronizado por `UseCaseResult`;
- tratamento explícito de erros conhecidos;
- tipagem completa.

## Fluxo Da Preparação Semântica

```text
UI Streamlit
↓
PrepareSemanticBaseCommand
↓
PrepareSemanticBaseUseCase.execute(...)
↓
text_chunker(...)
↓
embedding_generator(...)
↓
document_chunk_replacer(...)
↓
UseCaseResult[PrepareSemanticBaseOutput]
↓
UI renderiza mensagem e atualiza estado
```

O caso de uso preserva:

- documentos enviados pela UI;
- modelo de embedding configurado;
- chunking padrão existente;
- substituição dos chunks por documento;
- contagem de chunks indexados;
- interrupção em erros conhecidos de embeddings ou persistência.

## Fluxo Do Relatório Executivo Inteligente

```text
UI Streamlit
↓
IntelligentExecutiveReportCommand
↓
IntelligentExecutiveReportUseCase.execute(...)
↓
SemanticRetriever.retrieve(..., limit=10)
↓
generate_intelligent_executive_report(...)
↓
UseCaseResult[IntelligentExecutiveReportOutput]
↓
UI renderiza relatório e downloads existentes
```

O caso de uso preserva:

- filtro pelos documentos preparados;
- modelo de embedding;
- modelo de geração;
- consulta fixa do relatório executivo;
- limite fixo de 10 evidências;
- mensagens conhecidas de ausência de evidências e falha;
- formatos de download já existentes.

## Composition Roots

As dependências concretas continuam fora da camada `application`.

A montagem dos Use Cases fica nos builders:

- `src/synapse_ai/ui/analysis_use_cases.py`;
- `src/synapse_ai/ui/dashboard_use_cases.py`.

Assim, a UI continua responsável por entrada, validação simples, estado visual e renderização,
enquanto a orquestração dos fluxos fica na camada de aplicação.

## Compatibilidade

A decisão preserva:

- prompts;
- modelos;
- banco de dados;
- payloads;
- parâmetros de chunking;
- query executiva;
- limite de fontes;
- persistência;
- exportações Markdown e PDF;
- mensagens funcionais;
- contratos públicos existentes.

Não foram migrados nesta fase:

- upload de documentos;
- auditoria;
- read models;
- queries do Dashboard operacional;
- exportações CSV ou XLSX de outras telas.

## Consequências Positivas

- Redução de responsabilidade da UI.
- Fluxos residuais de IA ficam testáveis sem Streamlit.
- Maior coerência com a arquitetura incremental já adotada.
- Preparação melhor para migração futura para FastAPI, workers ou outra interface.
- Menor acoplamento entre interface, Supabase, OpenAI e serviços de IA.

## Consequências Negativas

- Mais arquivos na camada `application`.
- Mais builders de composição para manter.
- A UI ainda controla mensagens visuais, spinners e downloads, como consequência da preservação de
  comportamento.

## Alternativas Descartadas

### Manter Os Fluxos Na UI

Descartado porque manteria a última orquestração relevante de IA acoplada ao Streamlit.

### Criar Uma Engine Genérica De Indexação

Descartado porque a fase exigia apenas encapsular o fluxo existente, sem antecipar upload,
processamento assíncrono, filas ou workers.

### Migrar Upload, Auditoria E Read Models

Descartado porque ampliaria o escopo e poderia alterar comportamento fora dos fluxos residuais de IA.

### Alterar Consulta, Limites Ou Prompts

Descartado porque mudaria comportamento funcional, violando o objetivo da fase.

## Escopo Restrito Da Fase

Esta decisão implementa apenas a migração arquitetural dos fluxos residuais de IA para
`PrepareSemanticBaseUseCase` e `IntelligentExecutiveReportUseCase`. Nenhuma funcionalidade nova foi
adicionada.
