# ADR 0001 - Introdução Da Camada Application

## Status

Aceita

## Contexto

O Synapse AI já possuía uma separação relevante entre interface, serviços, clientes externos,
modelos e persistência. Porém, parte da orquestração dos fluxos de negócio ainda estava localizada
diretamente na camada de interface Streamlit.

O caso mais evidente era o fluxo de perguntas com RAG, em que a interface coordenava:

- validação da pergunta;
- geração de embedding da consulta;
- recuperação semântica de trechos documentais;
- construção das fontes;
- chamada ao modelo de linguagem;
- persistência opcional do histórico;
- tratamento de erros;
- renderização do resultado.

Essa concentração aumentava a responsabilidade da UI e dificultava a evolução futura do projeto
para outras interfaces, como FastAPI + React, workers assíncronos ou APIs externas.

## Problema

A interface estava assumindo responsabilidades de aplicação além de entrada e renderização.

Isso gerava riscos arquiteturais:

- aumento de acoplamento entre Streamlit e regras de orquestração;
- dificuldade para testar fluxos completos sem envolver UI;
- maior custo para migrar a aplicação para outra interface;
- tendência de crescimento excessivo dos arquivos de página;
- menor clareza sobre onde novos fluxos deveriam ser implementados.

## Decisão

Foi criada uma camada `application`, responsável por conter casos de uso da aplicação.

Essa camada fica entre a UI e os serviços existentes.

Na primeira fase, foi implementada apenas a infraestrutura da camada e um caso de uso completo:

- `AskQuestionUseCase`

Esse caso de uso passou a encapsular:

- recuperação de fontes;
- geração da resposta RAG;
- persistência opcional;
- tratamento de erros conhecidos;
- retorno estruturado para a UI.

A UI passa a chamar:

```text
result = ask_question_use_case.execute(...)
```

E permanece responsável apenas por:

- coletar entrada do usuário;
- fazer validações simples de tela;
- chamar o caso de uso;
- renderizar mensagens, respostas e fontes.

Todas as dependências do caso de uso são recebidas por construtor. O caso de uso não instancia
clientes, repositórios ou serviços internamente.

## Consequências

### Positivas

- Redução de responsabilidade da camada de UI.
- Maior testabilidade dos fluxos de aplicação.
- Melhor separação entre interface, orquestração e serviços de domínio.
- Menor acoplamento com Streamlit.
- Caminho mais claro para criação de novos casos de uso.
- Preparação arquitetural para futura migração para FastAPI + React.
- Preservação do comportamento atual, sem alteração de prompts, regras de negócio, banco ou modelos.

### Negativas

- Aumenta o número de arquivos e camadas do projeto.
- Exige disciplina para que novos fluxos não voltem a ser implementados diretamente na UI.
- Durante a transição, alguns wrappers temporários podem coexistir com a nova camada.
- A arquitetura ainda não fica completamente limpa até que os demais fluxos sejam migrados em fases futuras.

## Alternativas Descartadas

### Manter a orquestração na UI

Foi descartado porque manteria o alto acoplamento com Streamlit e continuaria dificultando testes,
manutenção e migração futura.

### Mover toda a aplicação para FastAPI imediatamente

Foi descartado por ser uma mudança grande demais para esta fase. O projeto já está funcional e a
decisão atual busca melhorar a arquitetura sem alterar comportamento nem trocar tecnologia de UI.

### Criar uma camada genérica de serviços maiores

Foi descartado porque apenas deslocaria a complexidade da UI para serviços amplos demais. A opção
por casos de uso torna cada fluxo explícito, testável e coeso.

### Refatorar todos os fluxos de análise de uma vez

Foi descartado para reduzir risco. A decisão desta fase foi criar a infraestrutura e migrar somente
um caso de uso completo, usando `AskQuestionUseCase` como padrão para fases posteriores.

