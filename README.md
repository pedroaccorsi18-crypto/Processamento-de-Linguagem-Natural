# Synapse AI

Synapse AI é um MVP acadêmico de Processamento de Linguagem Natural e Inteligência Organizacional. O projeto prepara uma plataforma para centralizar documentos organizacionais, estruturar conteúdo textual e, nas próximas fases, permitir consultas em linguagem natural com rastreabilidade das fontes.

## Problema de negócio

Organizações acumulam decisões, riscos, responsáveis e contexto em documentos dispersos. Isso dificulta auditoria, aprendizado institucional e tomada de decisão baseada em evidências.

## Objetivo acadêmico

Construir, de forma incremental, uma arquitetura de PLN capaz de receber documentos, organizar conhecimento e apoiar análises futuras com busca semântica, RAG e sínteses executivas.

## Estágio atual

Fase 2 — Data Layer.

Implementado até agora:

- aplicação Streamlit;
- autenticação com Supabase Auth;
- controle de sessão;
- páginas públicas e privadas;
- clientes Supabase e OpenAI centralizados;
- arquitetura modular em `src/synapse_ai`;
- schema SQL planejado para Supabase;
- testes automatizados;
- configuração de lint com Ruff.
- upload de PDF, DOCX, TXT e MD;
- extração textual local;
- metadados básicos;
- persistência inicial na tabela `documents`.

Ainda não implementado:

- embeddings;
- banco vetorial;
- RAG;
- chamadas automáticas à OpenAI.

## Stack

- Python 3.11 ou superior
- Streamlit
- Supabase Python SDK
- Supabase Auth
- OpenAI Python SDK
- pypdf
- python-docx
- pytest
- ruff

## Estrutura

```text
app.py
src/synapse_ai/
  auth/
  clients/
  models/
  services/
  ui/
  utils/
tests/
supabase/schema.sql
.streamlit/config.toml
.streamlit/secrets.example.toml
```

## Requisitos

- Python 3.11+
- Git
- Conta/projeto Supabase
- Chave OpenAI configurada localmente apenas quando as fases futuras exigirem uso real

## Instalação no Windows

Crie o ambiente virtual:

```powershell
py -3.11 -m venv .venv
```

Ative o ambiente:

```powershell
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Configuração de segredos

Crie um arquivo local `.streamlit/secrets.toml` com a estrutura abaixo. Não versione esse arquivo.

```toml
[supabase]
url = "https://SEU-PROJETO.supabase.co"
publishable_key = "sb_publishable_EXEMPLO"

[openai]
api_key = "sk-proj-EXEMPLO"
```

O repositório inclui `.streamlit/secrets.example.toml` apenas como exemplo sem credenciais reais.

## Supabase

1. Crie um projeto no Supabase.
2. Ative autenticação por e-mail e senha.
3. Copie a URL do projeto e a publishable key para `.streamlit/secrets.toml`.
4. Abra `supabase/schema.sql`.
5. Revise o SQL.
6. Execute manualmente no Supabase SQL Editor.

O script cria tabelas para `profiles`, `documents` e `analyses`, habilita Row Level Security e define políticas por usuário. Na Fase 2, `documents` também armazena o texto extraído, contagem de caracteres, metadados e data de processamento.

## Executar o app

```powershell
streamlit run app.py
```

## Testes

```powershell
pytest
```

Os testes usam mocks e fakes. Eles não acessam internet, não criam usuários reais e não consomem créditos.

## Lint

```powershell
ruff check .
```

## Roadmap

Fase 1 — Foundation

- arquitetura;
- autenticação;
- sessão;
- clientes;
- testes.

Fase 2 — Data Layer

- upload;
- extração;
- parsing;
- metadados;
- persistência.

Fase 3 — AI Layer

- chunking;
- embeddings;
- banco vetorial;
- busca semântica;
- RAG.

Fase 4 — Intelligence

- sínteses;
- riscos;
- inconsistências;
- insights;
- agentes especializados.

## Limitações

Esta versão entrega a fundação técnica e a camada inicial de dados. A página de upload processa documentos localmente e persiste texto/metadados no Supabase. A página de análises ainda não executa IA, embeddings ou RAG.
