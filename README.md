# Synapse AI

Synapse AI é um MVP acadêmico de Processamento de Linguagem Natural e Inteligência Organizacional. O projeto prepara uma plataforma para centralizar documentos organizacionais, estruturar conteúdo textual e permitir consultas em linguagem natural com rastreabilidade das fontes.

## Problema de negócio

Organizações acumulam decisões, riscos, responsáveis e contexto em documentos dispersos. Isso dificulta auditoria, aprendizado institucional e tomada de decisão baseada em evidências.

## Objetivo acadêmico

Construir, de forma incremental, uma arquitetura de PLN capaz de receber documentos, organizar conhecimento e apoiar análises com busca semântica, RAG e sínteses executivas.

## Estágio atual

Fase 4 inicial — Intelligence.

Implementado até agora:

- aplicação Streamlit;
- autenticação com Supabase Auth;
- controle de sessão;
- páginas públicas e privadas;
- clientes Supabase e OpenAI centralizados;
- arquitetura modular em `src/synapse_ai`;
- schema SQL planejado para Supabase;
- testes automatizados;
- configuração de lint com Ruff;
- upload de PDF, DOCX, TXT e MD;
- extração textual local;
- armazenamento privado do arquivo original para download futuro;
- metadados básicos;
- persistência inicial na tabela `documents`;
- chunking textual;
- geração de embeddings com OpenAI;
- tabela vetorial `document_chunks` com `pgvector`;
- busca semântica via função SQL `match_document_chunks`;
- seleção explícita de documentos para definir o escopo da análise;
- respostas em linguagem natural com fontes recuperadas;
- geração de planos de ação com fontes;
- extração estruturada de inteligência organizacional;
- identificação de decisões, riscos, inconsistências, pendências, prazos e responsáveis;
- comparação documental para detectar divergências entre arquivos;
- análise de sentimentos organizacionais, incluindo urgência, tensão, confiança, conflito e risco percebido;
- geração de alertas preventivos para prazos críticos, responsáveis ausentes, riscos e lacunas de evidência;
- reconhecimento de padrões históricos a partir de análises salvas;
- dashboard executivo;
- relatórios executivos com IA;
- auditoria de fontes com exportação em PDF e Markdown.

Ainda não implementado:

- conectores reais para Teams, Slack, Jira, e-mail e SharePoint;
- agentes especializados;
- alertas preventivos;
- versionamento avançado de documentos.

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
embedding_model = "text-embedding-3-small"
generation_model = "gpt-5-mini"
```

O repositório inclui `.streamlit/secrets.example.toml` apenas como exemplo sem credenciais reais.

## Supabase

1. Crie um projeto no Supabase.
2. Ative autenticação por e-mail e senha.
3. Copie a URL do projeto e a publishable key para `.streamlit/secrets.toml`.
4. Abra `supabase/schema.sql`.
5. Revise o SQL.
6. Execute manualmente no Supabase SQL Editor.

O script cria tabelas para `profiles`, `documents`, `document_chunks` e `analyses`, configura o bucket privado `documents`, habilita Row Level Security e define políticas por usuário. Na Fase 3, `document_chunks` armazena os trechos, embeddings e metadados usados pela busca semântica.

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
- sentimentos organizacionais;
- alertas preventivos;
- padrões históricos;
- insights;
- agentes especializados.

## Limitações

Esta versão entrega a fundação técnica, a camada inicial de dados e uma primeira camada RAG. A página de upload processa documentos localmente e persiste texto/metadados no Supabase. A página de análises depende do `schema.sql` atualizado, de documentos salvos e da preparação semântica dos documentos antes das perguntas.
