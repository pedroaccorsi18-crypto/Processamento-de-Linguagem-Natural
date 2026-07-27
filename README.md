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
- upload de PDF, DOCX, PPTX, XLSX, TXT, MD, CSV, JSON, VTT, EML e arquivos de áudio;
- transcrição automática de áudios para análise textual;
- ingestão estruturada de exportações de tickets/Jira em CSV e XLSX;
- ingestão estruturada de exportações de Slack em JSON;
- ingestão estruturada de mensagens e transcrições do Microsoft Teams em JSON e VTT;
- importação de arquivos de pastas compartilhadas do Google Drive via OAuth;
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
- orquestração multiagente real com agentes de decisões, riscos, consistência, sentimentos e governança;
- dashboard executivo;
- relatórios executivos com IA;
- auditoria de fontes com exportação em PDF e Markdown.

Ainda não implementado:

- conectores privados com OAuth para Teams, Slack, Jira, SharePoint, CRM e ERP além do Google Drive;
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
python -m pip install -e ".[dev]"
```

Para ambiente publicado, `requirements.txt` já instala o pacote local e as dependências de runtime.
O extra `.[dev]` é usado apenas para testes, lint e type checking no desenvolvimento.

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
transcription_model = "gpt-4o-mini-transcribe"

[app]
public_url = "http://localhost:8501"

[google_drive]
api_key = ""
client_id = "GOOGLE_OAUTH_CLIENT_ID_EXEMPLO"
client_secret = "GOOGLE_OAUTH_CLIENT_SECRET_EXEMPLO"
redirect_uri = "http://localhost:8501"
```

O repositório inclui `.streamlit/secrets.example.toml` apenas como exemplo sem credenciais reais.

Para produto real, o caminho recomendado para Google Drive é OAuth. A empresa cria um cliente OAuth
no Google Cloud, autoriza o Synapse AI e o sistema usa um token de acesso com escopo somente leitura
do Drive. A opção `google_drive.api_key` existe apenas como compatibilidade para demonstrações com
pastas compartilhadas.

## Supabase

1. Crie um projeto no Supabase.
2. Ative autenticação por e-mail e senha.
3. Copie a URL do projeto e a publishable key para `.streamlit/secrets.toml`.
4. Em produção, configure `app.public_url` com a URL pública do Synapse AI e cadastre a
   mesma URL em Authentication > URL Configuration no Supabase.
5. Abra `supabase/schema.sql`.
6. Revise o SQL.
7. Execute manualmente no Supabase SQL Editor.

O script cria tabelas para `profiles`, `documents`, `document_chunks` e `analyses`, configura o bucket privado `documents`, habilita Row Level Security e define políticas por usuário. Na Fase 3, `document_chunks` armazena os trechos, embeddings e metadados usados pela busca semântica.

## Executar o app

```powershell
streamlit run app.py
```

## Publicação web para apresentação

Para sair do `localhost`, o projeto deve ser publicado em um serviço web compatível com Streamlit.
URL pública da apresentação:

```text
https://synapse-ai-pnl.streamlit.app/
```

O fluxo recomendado para a apresentação é:

1. subir o repositório atualizado para o GitHub;
2. publicar o app em Streamlit Community Cloud, Render, Railway ou serviço equivalente;
3. configurar no ambiente web os mesmos segredos de `.streamlit/secrets.toml`;
4. manter Supabase como backend remoto;
5. cadastrar a URL pública do app como redirect URI autorizado no Google Cloud OAuth;
6. testar login, upload, Google Drive, preparação semântica, análises e download de relatórios na URL final.

Sem a URL pública cadastrada no Google Cloud, o OAuth do Google Drive continuará funcionando apenas no
endereço local configurado.

Guia detalhado: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
Roteiro de demonstração: [`docs/PRESENTATION_CHECKLIST.md`](docs/PRESENTATION_CHECKLIST.md).

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

Esta versão entrega a fundação técnica, a camada de dados, RAG e análises organizacionais avançadas.
A página de upload processa documentos localmente e persiste texto/metadados no Supabase. A página
de análises depende do `schema.sql` atualizado, de documentos salvos e da preparação semântica dos
documentos antes das perguntas.
