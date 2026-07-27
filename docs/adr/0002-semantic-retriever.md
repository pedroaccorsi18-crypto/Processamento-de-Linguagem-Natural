# ADR 0002 - Extração Do Semantic Retriever

## Status

Aceita

## Contexto

Na Fase 01, foi criada a camada `application` e o `AskQuestionUseCase` passou a centralizar o
fluxo de perguntas com RAG. Mesmo assim, o caso de uso ainda conhecia detalhes internos da
recuperação semântica.

Esse fluxo incluía:

- geração do embedding da consulta;
- chamada da busca vetorial;
- recuperação dos chunks;
- construção dos objetos `SourceSnippet`;
- retorno das fontes para geração da resposta.

Embora funcional, essa responsabilidade ainda era detalhada demais para um caso de uso. O
`AskQuestionUseCase` deveria coordenar passos de aplicação em alto nível, não conhecer a mecânica
interna da busca semântica.

## Problema

O caso de uso ainda estava acoplado aos detalhes da recuperação semântica.

Isso gerava riscos arquiteturais:

- duplicação futura do mesmo fluxo em outros casos de uso;
- dificuldade para evoluir a estratégia de recuperação sem impactar casos de uso;
- aumento de responsabilidade do `AskQuestionUseCase`;
- menor clareza sobre a fronteira entre orquestração de aplicação e infraestrutura semântica;
- mais pontos de alteração caso o RAG evolua para reranking, filtros adicionais ou múltiplas fontes.

## Decisão

Foi criado o componente `SemanticRetriever` em `application/retrieval`.

Ele encapsula completamente:

1. geração do embedding da consulta;
2. busca vetorial;
3. recuperação dos chunks;
4. construção dos `SourceSnippet`;
5. retorno da lista de fontes.

O `AskQuestionUseCase` passa a coordenar apenas três passos de alto nível:

```text
SemanticRetriever.retrieve()
↓
RAGAnswerGenerator()
↓
AnalysisSaver()
```

O `SemanticRetriever` recebe todas as dependências por construtor e não instancia OpenAI,
Supabase, repositórios ou serviços internamente.

## Consequências

### Positivas

- Redução da responsabilidade do `AskQuestionUseCase`.
- Reutilização da recuperação semântica por outros casos de uso.
- Menor acoplamento entre casos de uso e detalhes de RAG.
- Melhor testabilidade do pipeline de recuperação.
- Preparação para evoluções futuras como reranking, filtros avançados e estratégias híbridas.
- Preservação do comportamento atual da aplicação.

### Negativas

- Adição de mais um componente arquitetural.
- Necessidade de disciplina para que novos casos de uso reutilizem o `SemanticRetriever`.
- Durante a transição, pode haver compatibilidade temporária com dependências antigas do caso de uso.

## Alternativas Descartadas

### Manter a recuperação semântica dentro do `AskQuestionUseCase`

Foi descartado porque manteria o caso de uso acoplado a detalhes de embeddings, busca vetorial e
montagem de fontes.

### Criar uma pasta `rag/` diretamente em `services`

Foi descartado nesta fase porque o objetivo era organizar o fluxo no nível de aplicação, permitindo
que casos de uso dependam de uma interface reutilizável sem conhecer detalhes internos.

### Refatorar todos os fluxos RAG de uma vez

Foi descartado para reduzir risco. Esta fase move apenas o componente reutilizável de recuperação
semântica e adapta o `AskQuestionUseCase`, sem avançar sobre outros fluxos.

### Instanciar clientes dentro do retriever

Foi descartado por violar injeção de dependências e aumentar acoplamento com OpenAI, Supabase e
infraestrutura externa.

