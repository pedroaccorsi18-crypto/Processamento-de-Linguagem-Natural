# Synapse AI - Architecture Review

Projeto analisado: `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural`

Documento preparado para revisão técnica externa da arquitetura atual do projeto. Este levantamento descreve organização, responsabilidades, fluxos, dependências e riscos arquiteturais sem reproduzir o conteúdo interno dos arquivos.

## Escopo Da Revisão

- A análise considera a estrutura atual do projeto local.
- Nenhum código-fonte foi alterado, refatorado ou implementado para este documento.
- Arquivos de ambiente, cache e dependências locais foram identificados, mas não expandidos como parte da arquitetura-fonte.
- Arquivos sensíveis locais, como `.streamlit/secrets.toml`, não são listados como artefatos de revisão.

## Etapa 1 - Árvore Completa Do Projeto

```text
Processamento-de-Linguagem-Natural/
├── .agents/
├── .git/
├── .ruff_cache/
├── .streamlit/
│   ├── config.toml
│   └── secrets.example.toml
├── .venv/
├── output/
├── src/
│   ├── synapse_ai.egg-info/
│   └── synapse_ai/
│       ├── __init__.py
│       ├── config.py
│       ├── auth/
│       │   ├── __init__.py
│       │   ├── auth.py
│       │   ├── guards.py
│       │   └── session.py
│       ├── clients/
│       │   ├── __init__.py
│       │   ├── openai_client.py
│       │   └── supabase_client.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── analysis.py
│       │   ├── document.py
│       │   └── user.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── agent_service.py
│       │   ├── alert_service.py
│       │   ├── analysis_repository.py
│       │   ├── analysis_service.py
│       │   ├── audit_service.py
│       │   ├── chunk_repository.py
│       │   ├── chunking_service.py
│       │   ├── comparison_service.py
│       │   ├── document_repository.py
│       │   ├── document_service.py
│       │   ├── document_storage.py
│       │   ├── embedding_service.py
│       │   ├── intelligence_service.py
│       │   ├── pattern_service.py
│       │   ├── pdf_rendering.py
│       │   ├── report_service.py
│       │   ├── sentiment_service.py
│       │   └── spreadsheet_export.py
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── analysis_page.py
│       │   ├── audit_page.py
│       │   ├── dashboard_page.py
│       │   ├── home_page.py
│       │   ├── login_page.py
│       │   ├── navigation.py
│       │   ├── register_page.py
│       │   └── upload_page.py
│       └── utils/
│           ├── __init__.py
│           ├── logging_utils.py
│           └── validation.py
├── supabase/
│   └── schema.sql
├── tests/
│   ├── __init__.py
│   ├── test_agent_service.py
│   ├── test_alert_service.py
│   ├── test_analysis_repository.py
│   ├── test_analysis_service.py
│   ├── test_audit_service.py
│   ├── test_auth.py
│   ├── test_chunk_repository.py
│   ├── test_chunking_service.py
│   ├── test_clients.py
│   ├── test_comparison_service.py
│   ├── test_config.py
│   ├── test_dashboard_page.py
│   ├── test_document_repository.py
│   ├── test_document_service.py
│   ├── test_document_storage.py
│   ├── test_embedding_service.py
│   ├── test_guards.py
│   ├── test_intelligence_service.py
│   ├── test_pattern_service.py
│   ├── test_report_service.py
│   ├── test_sentiment_service.py
│   ├── test_session.py
│   └── test_smoke.py
├── tmp/
├── .gitignore
├── app.py
├── LICENSE
├── PROJECT_ARCHITECTURE.md
├── pyproject.toml
├── README.md
└── requirements.txt
```

Observacao: `.git/`, `.venv/`, `.ruff_cache/`, `output/`, `tmp/`, `src/synapse_ai.egg-info/` e caches Python sao diretorios locais, gerados ou operacionais. Eles foram considerados na arvore por existirem no projeto, mas nao representam modulos de arquitetura da aplicacao.

## Etapa 2 - Mapeamento Da Arquitetura

### Organizacao Geral

A aplicacao esta organizada como uma aplicacao Streamlit modular, com entrada central em `app.py` e pacote principal em `src/synapse_ai/`.

O projeto segue uma separacao por responsabilidades:

- interface: `src/synapse_ai/ui/`
- autenticacao e sessao: `src/synapse_ai/auth/`
- configuracao: `src/synapse_ai/config.py`
- clientes externos: `src/synapse_ai/clients/`
- modelos de dominio: `src/synapse_ai/models/`
- regras de negocio, RAG, IA, exportacoes e persistencia: `src/synapse_ai/services/`
- utilitarios transversais: `src/synapse_ai/utils/`
- banco de dados: `supabase/schema.sql`
- testes automatizados: `tests/`

### Camadas Existentes

#### 1. Camada De Entrada

Arquivo principal:

- `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\app.py`

Responsabilidade:

- iniciar a aplicacao Streamlit
- carregar configuracao
- configurar logs
- inicializar sessao
- renderizar navegacao
- rotear para paginas publicas e autenticadas

Essa camada conhece varias paginas da UI e funciona como controlador central da experiencia Streamlit.

#### 2. Camada De Configuracao

Arquivo principal:

- `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\config.py`

Responsabilidade:

- centralizar leitura e validacao de configuracoes
- fornecer credenciais e parametros para Supabase, OpenAI, modelos, limites e ambiente
- reduzir espalhamento de secrets e constantes pelo codigo

#### 3. Camada De Autenticacao E Sessao

Pasta:

- `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\auth\`

Responsabilidade:

- autenticar usuarios via Supabase
- representar usuario autenticado
- controlar estado de sessao no Streamlit
- proteger paginas autenticadas

#### 4. Camada De Clientes Externos

Pasta:

- `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\clients\`

Responsabilidade:

- criar clientes para OpenAI e Supabase
- isolar detalhes de inicializacao das dependencias externas
- permitir reaproveitamento dos clientes pelas paginas e servicos

#### 5. Camada De Interface

Pasta:

- `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\`

Responsabilidade:

- renderizar paginas Streamlit
- receber entradas do usuario
- chamar servicos de dominio
- apresentar respostas, tabelas, downloads, historicos, auditorias e dashboards

Arquivos com maior responsabilidade nessa camada:

- `analysis_page.py`
- `dashboard_page.py`
- `upload_page.py`
- `audit_page.py`
- `navigation.py`

#### 6. Camada De Servicos

Pasta:

- `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\`

Responsabilidade:

- implementar regras de negocio
- preparar documentos para IA
- extrair texto e metadados
- quebrar documentos em trechos
- gerar embeddings
- executar RAG
- produzir analises especializadas
- gerar alertas, comparacoes, padroes historicos, sentimento, relatorios e pacotes de evidencia
- persistir e recuperar documentos, chunks e analises

Essa e a camada mais densa do projeto.

#### 7. Camada De Modelos

Pasta:

- `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\models\`

Responsabilidade:

- representar entidades simples usadas pela aplicacao
- separar estruturas de usuario, documento e analise da UI

#### 8. Camada De Banco De Dados

Arquivo:

- `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\supabase\schema.sql`

Responsabilidade:

- definir estrutura Supabase/PostgreSQL
- definir tabelas, relacionamentos e recursos para persistencia
- viabilizar armazenamento de documentos, trechos, historicos e possivelmente vetores

#### 9. Camada De Utilitarios

Pasta:

- `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\utils\`

Responsabilidade:

- validacoes reutilizaveis
- configuracao auxiliar de logs

#### 10. Camada De Testes

Pasta:

- `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\tests\`

Responsabilidade:

- validar comportamento dos servicos, autenticacao, configuracao, repositorios, UI e fluxos criticos
- proteger evolucao incremental do projeto

### Como Os Modulos Conversam Entre Si

Fluxo principal de dependencia:

```text
app.py
  -> config.py
  -> auth/session.py
  -> ui/navigation.py
  -> ui/*.py
      -> clients/*.py
      -> services/*.py
      -> auth/session.py
      -> config.py
          -> models/*.py
          -> Supabase
          -> OpenAI
```

As paginas de UI funcionam como orquestradoras. Elas conhecem sessao, clientes externos e servicos. Os servicos concentram a logica de dominio, mas alguns tambem atuam como repositorios de persistencia.

### Arquivos Com Maior Responsabilidade

- `app.py`: entrada, bootstrapping e roteamento principal.
- `ui/analysis_page.py`: principal tela de IA, RAG, selecao documental, analises, exportacoes e interacao com OpenAI/Supabase.
- `ui/dashboard_page.py`: visao executiva e relatorios.
- `ui/upload_page.py`: entrada de documentos, extracao e persistencia inicial.
- `services/analysis_service.py`: construcao de respostas e artefatos analiticos.
- `services/analysis_repository.py`: historico e recuperacao de analises.
- `services/chunk_repository.py`: persistencia e busca de trechos documentais.
- `services/embedding_service.py`: embeddings e base semantica.
- `services/agent_service.py`: coordenacao de agentes especializados.
- `supabase/schema.sql`: contrato estrutural do banco.

### Padroes Arquiteturais Identificados

- Arquitetura em camadas: UI, servicos, clientes, modelos e banco.
- Service Layer: regras de negocio concentradas em `services/`.
- Repository Pattern parcial: arquivos `*_repository.py` encapsulam operacoes de persistencia.
- Client Factory simples: `clients/openai_client.py` e `clients/supabase_client.py`.
- RAG Pipeline: upload, extracao, chunking, embeddings, recuperacao semantica e resposta fundamentada.
- Modularizacao por pagina: cada tela Streamlit possui arquivo proprio.
- Data Transfer Models simples: modelos em `models/` representam estruturas do dominio.
- Export Services: geracao de PDF, planilhas e pacotes de evidencia isolada em servicos.

### Dependencias Entre Modulos

Dependencias mais relevantes:

- `app.py` depende de `config`, `auth.session`, `utils.logging_utils` e todas as paginas principais.
- Paginas em `ui/` dependem de `auth.session`, `config`, `clients` e `services`.
- `clients` dependem de `config`.
- `auth` depende de `models.user`.
- `document_service` depende de `models.document`.
- `analysis_service` e servicos especializados dependem de exportacao, estruturas de fonte e regras analiticas.
- `chunk_repository`, `document_repository` e `analysis_repository` aproximam servicos da persistencia Supabase.
- `pdf_rendering` e `spreadsheet_export` funcionam como servicos utilitarios de saida.

## Etapa 3 - Fluxo Real Da Aplicacao

### Fluxo De Abertura Do Sistema

```text
Usuario
↓
Streamlit
↓
app.py
↓
config.py
↓
logging_utils.py
↓
auth/session.py
↓
ui/navigation.py
↓
pagina publica ou area autenticada
```

Quando o usuario abre a aplicacao, o Streamlit executa `app.py`. O arquivo principal carrega configuracoes, inicializa logs, prepara sessao e chama a navegacao. A navegacao decide quais paginas aparecem conforme o estado autenticado.

### Fluxo De Autenticacao

```text
Usuario
↓
login_page.py ou register_page.py
↓
validation.py
↓
supabase_client.py
↓
auth/auth.py
↓
auth/session.py
↓
area autenticada
```

As paginas de login e cadastro validam entradas, usam o cliente Supabase e atualizam a sessao Streamlit. A partir disso, as paginas autenticadas ficam disponiveis.

### Fluxo De Upload Documental

```text
Usuario
↓
upload_page.py
↓
document_service.py
↓
document_storage.py
↓
document_repository.py
↓
Supabase
↓
documento salvo e texto extraido
```

O usuario envia um documento pela interface. A pagina de upload extrai texto e metadados por meio dos servicos documentais. O documento e suas informacoes sao persistidos usando os repositorios ligados ao Supabase.

### Fluxo De Preparacao Para IA

```text
Usuario
↓
analysis_page.py ou dashboard_page.py
↓
document_repository.py
↓
chunking_service.py
↓
embedding_service.py
↓
chunk_repository.py
↓
Supabase / base semantica
```

Quando o usuario atualiza a base semantica, os documentos selecionados sao divididos em trechos. Em seguida, embeddings sao gerados e armazenados. A base passa a estar pronta para consultas por similaridade.

### Fluxo De Pergunta E Resposta Com Fontes

```text
Usuario
↓
analysis_page.py
↓
openai_client.py
↓
embedding_service.py
↓
chunk_repository.py
↓
trechos relevantes
↓
analysis_service.py
↓
OpenAI
↓
resposta fundamentada
↓
analysis_repository.py
↓
historico salvo
↓
UI com resposta e fontes
```

A pergunta do usuario e transformada em embedding. O sistema recupera trechos semanticamente proximos na base documental. Esses trechos sao enviados como contexto ao modelo de linguagem. A resposta e apresentada com fontes e pode ser salva no historico.

### Fluxo De Analises Especializadas

```text
Documentos e respostas
↓
analysis_page.py / dashboard_page.py / audit_page.py
↓
servicos especializados
↓
OpenAI e/ou regras internas
↓
resultados estruturados
↓
exportacao ou historico
```

Servicos especializados:

- `agent_service.py`: agentes especializados.
- `alert_service.py`: alertas preventivos.
- `pattern_service.py`: padroes historicos.
- `comparison_service.py`: comparacao documental.
- `intelligence_service.py`: inteligencia organizacional.
- `sentiment_service.py`: sentimento e tom.
- `report_service.py`: relatorios executivos.
- `audit_service.py`: trilha de evidencias.

## Etapa 4 - Inventario Dos Arquivos

### Auth

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\auth\__init__.py`

- Responsabilidade: inicializar pacote de autenticacao.
- Quem utiliza: importacoes de pacote.
- Quem ele utiliza: nenhum modulo interno relevante.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\auth\auth.py`

- Responsabilidade: operacoes de autenticacao e construcao de usuario autenticado.
- Quem utiliza: `ui/login_page.py`, `ui/register_page.py`.
- Quem ele utiliza: `models/user.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\auth\guards.py`

- Responsabilidade: validacoes de acesso a areas protegidas.
- Quem utiliza: testes e possiveis fluxos protegidos.
- Quem ele utiliza: `auth/session.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\auth\session.py`

- Responsabilidade: controle da sessao Streamlit e usuario atual.
- Quem utiliza: `app.py`, `auth/guards.py`, `ui/analysis_page.py`, `ui/audit_page.py`, `ui/dashboard_page.py`, `ui/login_page.py`, `ui/upload_page.py`.
- Quem ele utiliza: `models/user.py`.

### Config

Nao existe uma pasta fisica `config/`. A responsabilidade esta centralizada em:

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\config.py`

- Responsabilidade: configuracao central da aplicacao, secrets, modelos, limites e parametros externos.
- Quem utiliza: `app.py`, `clients/openai_client.py`, `clients/supabase_client.py`, `ui/analysis_page.py`, `ui/audit_page.py`, `ui/dashboard_page.py`, `ui/login_page.py`, `ui/register_page.py`, `ui/upload_page.py`.
- Quem ele utiliza: nenhum modulo interno relevante.

### Database

Nao existe uma pasta fisica `database/`. A responsabilidade de banco esta em:

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\supabase\schema.sql`

- Responsabilidade: contrato do banco Supabase/PostgreSQL, tabelas, politicas e estruturas persistentes.
- Quem utiliza: ambiente Supabase e todos os repositorios que persistem dados.
- Quem ele utiliza: recursos SQL/PostgreSQL/Supabase.

### Models

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\models\__init__.py`

- Responsabilidade: inicializar pacote de modelos.
- Quem utiliza: importacoes de pacote.
- Quem ele utiliza: nenhum modulo interno relevante.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\models\analysis.py`

- Responsabilidade: estruturas relacionadas a analises.
- Quem utiliza: servicos e testes relacionados a analise.
- Quem ele utiliza: nenhum modulo interno relevante.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\models\document.py`

- Responsabilidade: estruturas de documento e metadados documentais.
- Quem utiliza: `services/document_service.py`.
- Quem ele utiliza: nenhum modulo interno relevante.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\models\user.py`

- Responsabilidade: representacao do usuario autenticado.
- Quem utiliza: `auth/auth.py`, `auth/session.py`.
- Quem ele utiliza: nenhum modulo interno relevante.

### Repositories

Nao existe uma pasta fisica `repositories/`. O padrao de repositorio esta implementado dentro de `services/`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\analysis_repository.py`

- Responsabilidade: persistir, recuperar e estruturar historico de analises.
- Quem utiliza: `ui/analysis_page.py`, `ui/audit_page.py`, `ui/dashboard_page.py`.
- Quem ele utiliza: `agent_service.py`, `alert_service.py`, `analysis_service.py`, `comparison_service.py`, `intelligence_service.py`, `pattern_service.py`, `sentiment_service.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\chunk_repository.py`

- Responsabilidade: persistir, substituir e consultar chunks documentais.
- Quem utiliza: `ui/analysis_page.py`, `ui/audit_page.py`, `ui/dashboard_page.py`, `ui/upload_page.py`.
- Quem ele utiliza: `chunking_service.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\document_repository.py`

- Responsabilidade: persistir e recuperar documentos e metadados.
- Quem utiliza: `ui/analysis_page.py`, `ui/dashboard_page.py`, `ui/upload_page.py`.
- Quem ele utiliza: `document_service.py`.

### Services

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\__init__.py`

- Responsabilidade: inicializar pacote de servicos.
- Quem utiliza: importacoes de pacote.
- Quem ele utiliza: nenhum modulo interno relevante.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\agent_service.py`

- Responsabilidade: coordenar agentes especializados e consolidar diagnosticos.
- Quem utiliza: `analysis_repository.py`, `ui/analysis_page.py`.
- Quem ele utiliza: `analysis_service.py`, `pattern_service.py`, `spreadsheet_export.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\alert_service.py`

- Responsabilidade: gerar alertas preventivos e exportacoes relacionadas.
- Quem utiliza: `analysis_repository.py`, `ui/analysis_page.py`.
- Quem ele utiliza: `analysis_service.py`, `spreadsheet_export.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\analysis_repository.py`

- Responsabilidade: gerenciar persistencia e historico de analises.
- Quem utiliza: `ui/analysis_page.py`, `ui/audit_page.py`, `ui/dashboard_page.py`.
- Quem ele utiliza: servicos especializados de analise.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\analysis_service.py`

- Responsabilidade: estruturar respostas, fontes, evidencias e artefatos analiticos.
- Quem utiliza: `agent_service.py`, `alert_service.py`, `comparison_service.py`, `intelligence_service.py`, `pattern_service.py`, `report_service.py`, `sentiment_service.py`, `ui/analysis_page.py`, `ui/dashboard_page.py`.
- Quem ele utiliza: `spreadsheet_export.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\audit_service.py`

- Responsabilidade: montar trilha de auditoria e evidencias.
- Quem utiliza: `ui/audit_page.py`.
- Quem ele utiliza: `pdf_rendering.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\chunk_repository.py`

- Responsabilidade: persistir e recuperar trechos documentais.
- Quem utiliza: paginas de analise, auditoria, dashboard e upload.
- Quem ele utiliza: `chunking_service.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\chunking_service.py`

- Responsabilidade: dividir documentos em trechos adequados para embeddings e RAG.
- Quem utiliza: `chunk_repository.py`, `ui/analysis_page.py`.
- Quem ele utiliza: nenhum modulo interno relevante.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\comparison_service.py`

- Responsabilidade: comparar documentos, gerar diferencas, riscos e planilhas estruturadas.
- Quem utiliza: `analysis_repository.py`, `ui/analysis_page.py`.
- Quem ele utiliza: `analysis_service.py`, `spreadsheet_export.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\document_repository.py`

- Responsabilidade: persistir documentos e metadados.
- Quem utiliza: `ui/analysis_page.py`, `ui/dashboard_page.py`, `ui/upload_page.py`.
- Quem ele utiliza: `document_service.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\document_service.py`

- Responsabilidade: extrair, normalizar e representar documentos.
- Quem utiliza: `document_repository.py`, `document_storage.py`, `ui/upload_page.py`.
- Quem ele utiliza: `models/document.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\document_storage.py`

- Responsabilidade: armazenar arquivos documentais e preparar recuperacao posterior.
- Quem utiliza: `ui/upload_page.py`.
- Quem ele utiliza: `document_service.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\embedding_service.py`

- Responsabilidade: gerar e manipular embeddings para busca semantica.
- Quem utiliza: `ui/analysis_page.py`, `ui/dashboard_page.py`.
- Quem ele utiliza: cliente/modelo externo de embeddings.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\intelligence_service.py`

- Responsabilidade: produzir inteligencia organizacional estruturada.
- Quem utiliza: `analysis_repository.py`, `ui/analysis_page.py`.
- Quem ele utiliza: `analysis_service.py`, `spreadsheet_export.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\pattern_service.py`

- Responsabilidade: identificar padroes historicos e recorrencias.
- Quem utiliza: `agent_service.py`, `analysis_repository.py`, `ui/analysis_page.py`.
- Quem ele utiliza: `analysis_service.py`, `spreadsheet_export.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\pdf_rendering.py`

- Responsabilidade: renderizar PDFs e saidas documentais.
- Quem utiliza: `audit_service.py`, `report_service.py`.
- Quem ele utiliza: bibliotecas de renderizacao PDF.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\report_service.py`

- Responsabilidade: gerar relatorios executivos e artefatos em PDF.
- Quem utiliza: `ui/dashboard_page.py`.
- Quem ele utiliza: `analysis_service.py`, `pdf_rendering.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\sentiment_service.py`

- Responsabilidade: avaliar sentimento, tom e sinais qualitativos.
- Quem utiliza: `analysis_repository.py`, `ui/analysis_page.py`.
- Quem ele utiliza: `analysis_service.py`, `spreadsheet_export.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\spreadsheet_export.py`

- Responsabilidade: gerar planilhas estruturadas para exportacao.
- Quem utiliza: `agent_service.py`, `alert_service.py`, `analysis_service.py`, `comparison_service.py`, `intelligence_service.py`, `pattern_service.py`, `sentiment_service.py`.
- Quem ele utiliza: bibliotecas de planilha.

### LLM

Nao existe uma pasta fisica `llm/`. As responsabilidades de LLM estao distribuidas entre cliente OpenAI, pagina de analise e servicos especializados.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\clients\openai_client.py`

- Responsabilidade: inicializar cliente OpenAI.
- Quem utiliza: `ui/analysis_page.py`, `ui/dashboard_page.py`.
- Quem ele utiliza: `config.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\embedding_service.py`

- Responsabilidade: gerar embeddings para busca semantica.
- Quem utiliza: `ui/analysis_page.py`, `ui/dashboard_page.py`.
- Quem ele utiliza: modelo externo de embeddings.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\analysis_service.py`

- Responsabilidade: estruturar respostas com fontes e evidencias.
- Quem utiliza: servicos especializados e paginas de analise.
- Quem ele utiliza: `spreadsheet_export.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\agent_service.py`

- Responsabilidade: coordenar analises especializadas em formato de agentes.
- Quem utiliza: `analysis_repository.py`, `ui/analysis_page.py`.
- Quem ele utiliza: `analysis_service.py`, `pattern_service.py`, `spreadsheet_export.py`.

### RAG

Nao existe uma pasta fisica `rag/`. O pipeline RAG esta distribuido nestes arquivos:

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\chunking_service.py`

- Responsabilidade: preparar trechos para recuperacao.
- Quem utiliza: `chunk_repository.py`, `ui/analysis_page.py`.
- Quem ele utiliza: nenhum modulo interno relevante.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\chunk_repository.py`

- Responsabilidade: armazenar e recuperar chunks.
- Quem utiliza: `ui/analysis_page.py`, `ui/audit_page.py`, `ui/dashboard_page.py`, `ui/upload_page.py`.
- Quem ele utiliza: `chunking_service.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\embedding_service.py`

- Responsabilidade: gerar vetores semanticos.
- Quem utiliza: `ui/analysis_page.py`, `ui/dashboard_page.py`.
- Quem ele utiliza: modelo externo de embedding.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\analysis_page.py`

- Responsabilidade: orquestrar consulta, recuperacao, resposta e persistencia.
- Quem utiliza: `app.py`.
- Quem ele utiliza: auth, config, clientes OpenAI/Supabase, repositorios e servicos de IA.

### UI

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\__init__.py`

- Responsabilidade: inicializar pacote de UI.
- Quem utiliza: importacoes de pacote.
- Quem ele utiliza: nenhum modulo interno relevante.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\analysis_page.py`

- Responsabilidade: tela principal de perguntas, RAG, analises inteligentes, selecao documental, historico e exportacoes.
- Quem utiliza: `app.py`.
- Quem ele utiliza: `auth/session.py`, `clients/openai_client.py`, `clients/supabase_client.py`, `config.py`, `agent_service.py`, `alert_service.py`, `analysis_repository.py`, `analysis_service.py`, `chunk_repository.py`, `chunking_service.py`, `comparison_service.py`, `document_repository.py`, `embedding_service.py`, `intelligence_service.py`, `pattern_service.py`, `sentiment_service.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\audit_page.py`

- Responsabilidade: tela de auditoria, trilha de evidencias e verificacao historica.
- Quem utiliza: `app.py`.
- Quem ele utiliza: `auth/session.py`, `clients/supabase_client.py`, `config.py`, `analysis_repository.py`, `audit_service.py`, `chunk_repository.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\dashboard_page.py`

- Responsabilidade: dashboard executivo, relatorios e visoes consolidadas.
- Quem utiliza: `app.py`.
- Quem ele utiliza: `auth/session.py`, `clients/openai_client.py`, `clients/supabase_client.py`, `config.py`, `analysis_repository.py`, `analysis_service.py`, `chunk_repository.py`, `document_repository.py`, `embedding_service.py`, `report_service.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\home_page.py`

- Responsabilidade: pagina inicial publica.
- Quem utiliza: `app.py`.
- Quem ele utiliza: Streamlit e conteudo de apresentacao.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\login_page.py`

- Responsabilidade: autenticacao de usuario.
- Quem utiliza: `app.py`.
- Quem ele utiliza: `auth/auth.py`, `auth/session.py`, `clients/supabase_client.py`, `config.py`, `utils/validation.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\navigation.py`

- Responsabilidade: navegacao entre paginas publicas e autenticadas.
- Quem utiliza: `app.py`.
- Quem ele utiliza: Streamlit e estado de navegacao.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\register_page.py`

- Responsabilidade: cadastro de usuario.
- Quem utiliza: `app.py`.
- Quem ele utiliza: `auth/auth.py`, `clients/supabase_client.py`, `config.py`, `utils/validation.py`.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\upload_page.py`

- Responsabilidade: envio, extracao, salvamento e listagem inicial de documentos.
- Quem utiliza: `app.py`.
- Quem ele utiliza: `auth/session.py`, `clients/supabase_client.py`, `config.py`, `chunk_repository.py`, `document_repository.py`, `document_service.py`, `document_storage.py`.

### Utils

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\utils\__init__.py`

- Responsabilidade: inicializar pacote de utilitarios.
- Quem utiliza: importacoes de pacote.
- Quem ele utiliza: nenhum modulo interno relevante.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\utils\logging_utils.py`

- Responsabilidade: configuracao auxiliar de logs.
- Quem utiliza: `app.py`.
- Quem ele utiliza: bibliotecas padrao de logging.

#### `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\utils\validation.py`

- Responsabilidade: validacoes reutilizaveis de entrada.
- Quem utiliza: `ui/login_page.py`, `ui/register_page.py`.
- Quem ele utiliza: nenhum modulo interno relevante.

## Etapa 5 - Top 20 Arquivos Mais Importantes

1. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\app.py`
   - Responsabilidade: ponto de entrada, inicializacao e roteamento.
   - Importancia: define o fluxo principal e conecta todas as paginas.

2. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\config.py`
   - Responsabilidade: configuracao central.
   - Importancia: todos os clientes e paginas dependem de configuracao correta.

3. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\supabase\schema.sql`
   - Responsabilidade: estrutura de persistencia.
   - Importancia: contrato real entre aplicacao e banco.

4. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\analysis_page.py`
   - Responsabilidade: tela central de IA e RAG.
   - Importancia: maior orquestrador funcional do sistema.

5. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\analysis_service.py`
   - Responsabilidade: resposta, fontes e evidencias.
   - Importancia: base da inteligencia aplicada aos documentos.

6. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\chunk_repository.py`
   - Responsabilidade: persistencia e recuperacao de chunks.
   - Importancia: componente essencial do RAG.

7. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\embedding_service.py`
   - Responsabilidade: embeddings.
   - Importancia: viabiliza busca semantica.

8. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\analysis_repository.py`
   - Responsabilidade: historico de analises.
   - Importancia: permite rastreabilidade e auditoria.

9. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\document_service.py`
   - Responsabilidade: extracao e normalizacao documental.
   - Importancia: entrada de dados do pipeline.

10. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\document_repository.py`
    - Responsabilidade: persistencia de documentos.
    - Importancia: base para reuso e historico documental.

11. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\agent_service.py`
    - Responsabilidade: agentes especializados.
    - Importancia: camada avancada de diagnostico.

12. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\alert_service.py`
    - Responsabilidade: alertas preventivos.
    - Importancia: transforma analise em antecipacao de risco.

13. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\pattern_service.py`
    - Responsabilidade: padroes historicos.
    - Importancia: suporta aprendizado organizacional.

14. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\intelligence_service.py`
    - Responsabilidade: inteligencia organizacional.
    - Importancia: produz sintese executiva e leitura estrategica.

15. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\comparison_service.py`
    - Responsabilidade: comparacao documental.
    - Importancia: identifica divergencias, mudancas e riscos.

16. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\sentiment_service.py`
    - Responsabilidade: leitura de sentimento e tom.
    - Importancia: amplia analise para aspectos qualitativos.

17. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\dashboard_page.py`
    - Responsabilidade: visao executiva.
    - Importancia: ponto de consolidacao para usuario final.

18. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\upload_page.py`
    - Responsabilidade: upload e salvamento documental.
    - Importancia: porta de entrada dos dados.

19. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\report_service.py`
    - Responsabilidade: relatorios executivos em PDF.
    - Importancia: materializa resultados para apresentacao.

20. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\audit_service.py`
    - Responsabilidade: trilha de evidencias.
    - Importancia: sustenta confiabilidade, revisao e governanca.

## Etapa 6 - Relatorio De Escalabilidade

### Acoplamento

O projeto possui acoplamento moderado. A organizacao em pastas e camadas ajuda bastante, mas algumas paginas de UI, especialmente `analysis_page.py`, conhecem muitos servicos, clientes e detalhes de fluxo. Isso torna a tela poderosa, mas tambem aumenta a dependencia entre interface e regras de negocio.

### Coesao

A coesao e boa nos servicos especializados. Arquivos como `comparison_service.py`, `sentiment_service.py`, `pattern_service.py` e `alert_service.py` possuem responsabilidades bem delimitadas. A coesao e menor nos pontos de orquestracao, onde multiplos fluxos se encontram.

### Organizacao

A organizacao geral e clara para um projeto academico avancado e ja se aproxima de uma arquitetura profissional. O pacote `src/synapse_ai/` separa corretamente UI, auth, clients, services, models e utils.

### Modularizacao

A modularizacao e um ponto forte. O projeto nao esta concentrado em um unico arquivo. Ha separacao efetiva entre upload, analise, dashboard, auditoria, relatorios e servicos de inteligencia.

### Separacao De Responsabilidades

A separacao e boa, mas ainda existe mistura parcial entre orquestracao de UI e regra de negocio. O Streamlit naturalmente incentiva paginas com bastante logica, mas para crescimento futuro seria interessante deslocar fluxos de caso de uso para uma camada de aplicacao.

### Reutilizacao

Ha boa reutilizacao em `spreadsheet_export.py`, `pdf_rendering.py`, `analysis_service.py` e servicos especializados. A existencia de testes para muitos servicos tambem indica que as funcoes foram pensadas para uso isolado.

### Facilidade De Manutencao

A manutencao tende a ser boa para ajustes pontuais em servicos. A manutencao de fluxos completos pode exigir cuidado maior por causa da dependencia das paginas Streamlit em varios servicos.

### Facilidade Para Testes

O projeto demonstra boa testabilidade, pois ha testes para configuracao, autenticacao, repositorios, servicos e partes de UI. Servicos puros sao mais faceis de testar. Fluxos integrados com Streamlit, Supabase e OpenAI exigem mocks ou testes de integracao controlados.

### Facilidade Para Adicionar Novas Funcionalidades

A arquitetura favorece novas funcionalidades quando elas cabem como novo servico especializado. Exemplos: novo agente, novo relatorio, novo tipo de exportacao ou nova analise. A dificuldade cresce quando a funcionalidade exige novo fluxo compartilhado entre varias paginas.

### Facilidade Para Migrar De Streamlit Para FastAPI + React

A migracao e viavel, mas exigiria separar explicitamente casos de uso hoje orquestrados em paginas Streamlit. Pontos favoraveis:

- servicos ja estao separados da UI
- clientes externos estao isolados
- modelos existem
- repositorios ja encapsulam parte da persistencia

Pontos que exigiriam trabalho:

- extrair logica de `analysis_page.py`, `dashboard_page.py`, `upload_page.py` e `audit_page.py` para uma camada de aplicacao
- transformar sessao Streamlit em autenticacao baseada em API
- converter estados de tela em endpoints e contratos JSON
- criar DTOs claros para frontend React
- padronizar respostas de erro e autorizacao

## Etapa 7 - Diagnostico Tecnico

### Pontos Fortes

- Separacao clara entre UI, servicos, clientes, modelos e autenticacao.
- Pipeline RAG identificavel e modular.
- Uso de Supabase como backend persistente.
- Historico de analises e trilha de evidencias, importantes para governanca.
- Exportacoes executivas em PDF e planilhas.
- Presenca de testes para muitas partes criticas.
- Projeto evoluiu alem de uma demonstracao simples, com funcionalidades analiticas reais.

### Pontos Fracos

- `analysis_page.py` concentra muita orquestracao.
- Nao ha pastas fisicas separadas para `repositories`, `database`, `llm` e `rag`; essas responsabilidades existem, mas estao distribuidas.
- Algumas fronteiras entre servico de dominio, repositorio e caso de uso ainda poderiam ser mais explicitas.
- Dependencia forte do Streamlit como camada de estado e navegacao.

### Gargalos

- Crescimento da pagina de analise pode dificultar manutencao.
- Chamadas a OpenAI e Supabase podem se tornar pontos de latencia.
- Geração de embeddings e atualizacao de base semantica podem pesar com muitos documentos.
- Operacoes de exportacao PDF/planilha podem ficar lentas com historicos grandes.

### Possiveis Dividas Tecnicas

- Ausencia de camada formal de casos de uso.
- Repositorios dentro de `services/`, em vez de uma camada fisica propria.
- RAG distribuido entre UI e servicos, sem modulo dedicado.
- Necessidade futura de contratos de entrada e saida mais rigorosos.
- Necessidade futura de politicas de privacidade e retencao de historico mais explicitas.

### Partes Muito Bem Implementadas

- Modularizacao de servicos especializados.
- Separacao dos clientes OpenAI e Supabase.
- Existencia de servicos de exportacao reutilizaveis.
- Estrutura de testes ampla para o porte do projeto.
- Preocupacao com auditoria, evidencias e rastreabilidade.

### Partes Que Merecem Atencao

- `ui/analysis_page.py`: principal candidato a divisao futura.
- `services/analysis_repository.py`: concentra relacao com muitos servicos especializados.
- `services/agent_service.py`: precisa manter fronteira clara entre agentes reais, heuristicas e simulacoes.
- `supabase/schema.sql`: deve permanecer sincronizado com repositorios e funcionalidades novas.
- Fluxo de sessao: precisa ser robusto para evitar mensagens de erro pouco profissionais ao usuario.

### Riscos Futuros

- Dificuldade de escalar para muitos usuarios simultaneos usando apenas Streamlit.
- Aumento de custo e latencia com documentos grandes e muitas perguntas.
- Crescimento excessivo das paginas UI.
- Inconsistencias entre schema do Supabase e codigo.
- Necessidade de governanca forte para historicos, documentos e confidencialidade.

## Etapa 8 - Roteiro De Leitura Para Um Arquiteto

1. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\README.md`
2. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\PROJECT_ARCHITECTURE.md`
3. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\pyproject.toml`
4. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\requirements.txt`
5. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\app.py`
6. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\config.py`
7. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\supabase\schema.sql`
8. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\auth\session.py`
9. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\auth\auth.py`
10. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\clients\supabase_client.py`
11. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\clients\openai_client.py`
12. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\navigation.py`
13. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\login_page.py`
14. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\register_page.py`
15. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\upload_page.py`
16. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\document_service.py`
17. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\document_storage.py`
18. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\document_repository.py`
19. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\chunking_service.py`
20. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\embedding_service.py`
21. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\chunk_repository.py`
22. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\analysis_page.py`
23. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\analysis_service.py`
24. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\analysis_repository.py`
25. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\agent_service.py`
26. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\alert_service.py`
27. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\pattern_service.py`
28. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\intelligence_service.py`
29. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\comparison_service.py`
30. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\sentiment_service.py`
31. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\dashboard_page.py`
32. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\report_service.py`
33. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\ui\audit_page.py`
34. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\audit_service.py`
35. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\pdf_rendering.py`
36. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\services\spreadsheet_export.py`
37. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\utils\validation.py`
38. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\src\synapse_ai\utils\logging_utils.py`
39. `C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\tests\`

## Etapa 9 - Exportacao

Arquivo gerado:

`C:\Users\Pedro\Downloads\Processamento-de-Linguagem-Natural\ARCHITECTURE_REVIEW.md`

