# Semantic Retrieval

A camada `application/retrieval` encapsula a recuperação semântica usada pelos casos de uso.

## Responsabilidade

O `SemanticRetriever` executa o fluxo completo de recuperação de fontes:

1. gerar o embedding da consulta;
2. executar a busca vetorial;
3. recuperar os chunks relevantes;
4. construir objetos `SourceSnippet`;
5. retornar a lista de fontes para o caso de uso.

Casos de uso não devem conhecer os detalhes internos desse fluxo.

## Fluxo

```text
Use Case
↓
SemanticRetriever.retrieve(...)
↓
EmbeddingGenerator
↓
ChunkMatcher
↓
SourceBuilder
↓
list[SourceSnippet]
```

## Dependências

O `SemanticRetriever` recebe todas as dependências por construtor:

- `embedding_generator`;
- `chunk_matcher`;
- `source_builder`.

Ele não instancia clientes, serviços, repositórios, OpenAI ou Supabase internamente.

## Reutilização Futura

Qualquer caso de uso que precise recuperar fontes documentais deve reutilizar o
`SemanticRetriever`. Isso evita duplicação de lógica de RAG, mantém a busca semântica testável
e permite alterar detalhes internos de recuperação sem modificar os casos de uso.

