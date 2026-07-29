# Synapse AI - README completo do projeto

Data de consolidação: 29 de julho de 2026

## Visão geral

O Synapse AI é uma plataforma de inteligência organizacional baseada em Processamento de Linguagem Natural, RAG e orquestração de IA. O objetivo do projeto é transformar documentos corporativos dispersos em uma base pesquisável, auditável e acionável, permitindo que usuários façam perguntas, gerem análises, identifiquem riscos e acompanhem evidências com rastreabilidade.

O projeto começou como um MVP acadêmico em Streamlit e evoluiu para uma arquitetura SaaS B2B mais profissional, com frontend em Next.js, backend em FastAPI, Supabase como camada de dados e OpenAI como motor de IA.

## Problema que o projeto resolve

Empresas acumulam conhecimento em PDFs, atas, planilhas, transcrições, mensagens, apresentações e arquivos exportados de sistemas. Esse conhecimento fica espalhado, difícil de consultar e pouco reutilizável. O Synapse AI busca reduzir esse atrito ao:

- centralizar documentos e fontes corporativas;
- extrair texto e metadados;
- preparar uma base semântica;
- permitir perguntas com fontes;
- gerar planos de ação e relatórios;
- detectar riscos, inconsistências, prazos e responsáveis;
- preservar histórico de análises;
- apoiar auditoria e tomada de decisão baseada em evidências.

## Arquitetura atual

O projeto possui três blocos principais:

1. Frontend moderno em Next.js
2. Backend API em FastAPI
3. Núcleo Python reutilizável em `src/synapse_ai`

A versão Streamlit continua no repositório como referência funcional e histórica, mas a direção atual do produto é a migração para Next.js + FastAPI.

### Frontend

Local: `frontend/`

Tecnologias:

- Next.js 15
- React 19
- TypeScript
- TailwindCSS
- Supabase Auth no cliente
- Playwright para homologação ponta a ponta

Páginas principais:

- `/` - entrada pública e autenticação;
- `/dashboard` - visão executiva;
- `/upload` - base documental e conectores;
- `/studio` - Estúdio de IA;
- `/insights` - inteligência consolidada;
- `/audit` - evidências e auditoria;
- `/about`, `/privacy`, `/terms` - páginas públicas de marca, privacidade e termos.

Componentes importantes:

- `frontend/components/app-shell.tsx` - estrutura geral da aplicação autenticada;
- `frontend/components/auth-gate.tsx` - proteção de páginas privadas;
- `frontend/components/copilot-chat.tsx` - interface do Copiloto;
- `frontend/components/kpi-card.tsx` - cartões executivos;
- `frontend/services/api.ts` - camada de comunicação com o backend.

### Backend

Local: `backend/`

Tecnologias:

- FastAPI
- Pydantic
- Uvicorn
- Supabase Python SDK
- OpenAI Python SDK
- CORS configurável por ambiente

Rotas principais:

- `GET /health` - verificação leve de saúde para monitoramento e keep-alive;
- `GET /api/dashboard/stats` - estatísticas executivas;
- `GET /api/documents` - listagem de documentos do usuário;
- `POST /api/documents/upload` - upload e persistência de documentos;
- `GET /api/documents/{document_id}/download` - download do arquivo original;
- `GET /api/integrations` - estado dos conectores corporativos;
- rotas OAuth do Google Drive;
- rotas OAuth do Slack;
- rotas previstas para Microsoft Teams e SharePoint;
- `GET /api/studio/documents` - documentos disponíveis no Estúdio;
- `GET /api/studio/history` - histórico de análises;
- `POST /api/studio/prepare` - preparação semântica;
- `POST /api/studio/analyses/{workflow}` - execução de fluxos de IA;
- `POST /api/copilot` - Copiloto contextual.

### Núcleo de domínio e aplicação

Local: `src/synapse_ai/`

Camadas principais:

- `application/` - casos de uso e orquestração de aplicação;
- `services/` - integrações, parsing, repositórios e serviços de domínio;
- `clients/` - clientes centralizados de Supabase e OpenAI;
- `models/` - modelos internos;
- `auth/` - autenticação e sessão;
- `ui/` - interface Streamlit legada e referência de funcionalidades;
- `utils/` - validações e utilitários.

Casos de uso já estruturados:

- pergunta com fontes;
- plano de ação;
- comparação documental;
- análise de sentimentos;
- alertas preventivos;
- padrões históricos;
- snapshot de inteligência;
- relatório multiagente;
- preparação da base semântica.

## Funcionalidades implementadas

### Autenticação e isolamento de usuários

- Login e cadastro com Supabase Auth.
- Sessão autenticada no frontend.
- Backend exige token do usuário nas rotas protegidas.
- Dados filtrados por usuário.
- Supabase com Row Level Security planejado no `schema.sql`.

### Upload e ingestão documental

Formatos previstos e suportados no pipeline:

- PDF
- DOCX
- PPTX
- XLSX
- TXT
- MD
- CSV
- JSON
- VTT
- EML
- MP3
- M4A
- WAV

O sistema:

- extrai texto;
- calcula tamanho e contagem de caracteres;
- salva metadados;
- guarda o arquivo original em storage privado;
- permite download futuro quando o arquivo original está disponível;
- evita duplicidades por conteúdo;
- mantém documentos isolados por conta.

### Base semântica e RAG

O pipeline de IA inclui:

- chunking textual;
- geração de embeddings com OpenAI;
- persistência em `document_chunks`;
- busca vetorial com `pgvector`;
- seleção explícita de documentos no escopo;
- resposta com fontes recuperadas;
- histórico de análises.

### Estúdio de IA

O Estúdio concentra as funções inteligentes de análise:

- perguntas com fontes;
- plano de ação;
- inteligência organizacional;
- comparação documental;
- sentimentos organizacionais;
- alertas preventivos;
- padrões históricos;
- relatório multiagente.

Status atual: a migração para FastAPI + Next.js foi iniciada e os endpoints do Estúdio já estão estruturados. A validação final de todos os fluxos reais ainda precisa ser feita ponta a ponta em produção.

### Copiloto

O Copiloto já possui:

- interface conversacional;
- histórico em sessão;
- chamada real para OpenAI;
- contexto da área aberta;
- integração via rota `POST /api/copilot`.

Ponto de melhoria: transformar o Copiloto em assistente transversal mais forte, com acesso contextual a métricas, documentos e ações do produto, sem ficar limitado a uma aba isolada.

### Dashboard, insights e auditoria

O projeto possui:

- dashboard executivo;
- métricas de base pronta, evidências e riscos;
- página de insights organizacionais;
- trilha de evidências;
- exportações em PDF, Markdown e planilhas;
- histórico de análises e fontes.

Ponto de melhoria: consolidar visualmente as informações para evitar excesso de blocos e melhorar a leitura executiva.

## Conectores corporativos

### Google Drive

Status: disponível.

O Google Drive usa OAuth, credenciais protegidas no backend e conexão vinculada à conta do usuário. O app OAuth foi colocado em produção no Google Cloud.

Ponto pendente: verificação completa de marca do Google, caso o produto use domínio próprio e precise aparecer como aplicativo verificado.

### Slack

Status: disponível e validado.

O Slack usa OAuth e escopos somente leitura. O app precisa ser adicionado aos canais que serão importados. Esse comportamento é correto e evita acesso involuntário a canais não autorizados.

Escopos configurados:

- `channels:read`
- `channels:history`
- `groups:read`
- `groups:history`
- `files:read`

### Microsoft Teams e SharePoint

Status: interface e rotas preparadas, ativação bloqueada por permissão externa.

Para ativar Teams e SharePoint, é necessário registrar um aplicativo no Microsoft Entra ID de uma organização com Microsoft 365. A conta acadêmica testada não possui permissão para criar app registrations.

Próximo passo necessário:

- obter permissão `Application Developer` no Entra ID;
- ou pedir para o administrador criar o app;
- configurar `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID` e `MICROSOFT_REDIRECT_URI` no Render.

### Jira, CRM e ERP

Status: previstos para evolução futura.

Hoje o sistema aceita ingestão de arquivos exportados, mas conectores diretos para Jira, CRM e ERP ainda não estão implementados.

## Banco de dados e Supabase

Arquivo principal:

- `supabase/schema.sql`

Recursos previstos:

- perfis de usuário;
- documentos;
- chunks semânticos;
- análises;
- conexões de integrações criptografadas;
- storage privado;
- Row Level Security;
- políticas por usuário;
- função SQL para busca vetorial.

Observação: sempre que o `schema.sql` mudar, ele precisa ser executado no SQL Editor do Supabase no projeto correto.

## Deploy e infraestrutura

### Frontend

Plataforma: Vercel

URL pública:

- `https://processamento-de-linguagem-natural.vercel.app`

### Backend

Plataforma: Render

URL pública:

- `https://synapse-ai-api-prod.onrender.com`

Health check:

- `https://synapse-ai-api-prod.onrender.com/health`

### Keep-alive

O GitHub Actions consulta a rota `/health` a cada cinco minutos para reduzir hibernação do Render.

Workflow:

- `.github/workflows/keep-render-awake.yml`

Também existe envio de alerta por e-mail em caso de falha, usando secrets do GitHub.

## Segurança

Boas práticas já aplicadas:

- segredos fora do Git;
- tokens OAuth criptografados;
- conectores somente leitura;
- backend como guardião dos client secrets;
- frontend sem chaves sensíveis;
- autenticação obrigatória nas rotas protegidas;
- isolamento por usuário;
- service role reservada para automação de QA, fora de Vercel e Render.

Recomendação importante:

Como algumas credenciais foram usadas durante configuração e testes, é prudente rotacionar chaves sensíveis antes de uma demonstração pública mais ampla ou antes de transformar o projeto em produto comercial.

## Testes e qualidade

Testes existentes:

- testes unitários Python com `pytest`;
- lint com `ruff`;
- type checking no frontend com TypeScript;
- lint do frontend com ESLint;
- build de produção do Next.js;
- testes E2E com Playwright.

Áreas cobertas:

- autenticação;
- upload;
- documentos;
- repositórios;
- chunks;
- embeddings;
- RAG;
- casos de uso;
- serviços de conectores;
- dashboard;
- Copiloto;
- API backend;
- isolamento entre usuários em E2E.

## Estado atual do produto

O projeto já deixou de ser apenas um protótipo local. Ele possui:

- produto publicado na web;
- backend próprio;
- frontend moderno;
- autenticação;
- upload real;
- IA conectada;
- base semântica;
- conectores Google Drive e Slack;
- preparação para Microsoft 365;
- documentação técnica;
- testes automatizados;
- pipeline de deploy.

O ponto principal agora não é mais provar que a ideia funciona. A ideia funciona. O foco restante é consolidar, testar e polir a experiência final.

## O que ainda falta

### Itens críticos antes da entrega

- validar ponta a ponta todos os fluxos do Estúdio de IA no frontend Next.js;
- confirmar que o backend atual em produção está respondendo corretamente para cada workflow;
- revisar mensagens de erro e loading states;
- executar uma bateria E2E final;
- garantir que a demonstração tenha dados de exemplo consistentes;
- gerar roteiro de apresentação.

### Itens importantes, mas não bloqueantes

- finalizar Microsoft Teams e SharePoint quando houver permissão no Entra ID;
- melhorar o Copiloto para ser transversal e contextual em todas as telas;
- refinar o Dashboard e Insights para reduzir excesso visual;
- criar domínio próprio;
- concluir verificação de marca no Google;
- ampliar conectores para Jira, CRM e ERP.

## Estimativa de conclusão

Minha avaliação atual:

- MVP acadêmico demonstrável: 85% a 90% concluído.
- Produto polido para apresentação excelente: 75% a 80% concluído.
- Produto SaaS comercial robusto: 55% a 65% concluído.

Para a entrega acadêmica, o projeto já está muito forte. O que falta é menos "inventar funcionalidade" e mais fechar o ciclo com estabilidade, clareza de uso e uma demonstração bem ensaiada.

## Recomendação de prioridade

Ordem recomendada para finalizar:

1. Validar Estúdio de IA no Next.js com backend real.
2. Rodar E2E completo.
3. Preparar dados de demonstração.
4. Refinar Copiloto e mensagens de orientação.
5. Lapidar Dashboard e Insights.
6. Preparar roteiro de apresentação.
7. Rotacionar credenciais sensíveis antes de exposição pública maior.

## Conclusão

O Synapse AI já possui densidade técnica acima do padrão esperado para um projeto acadêmico: arquitetura desacoplada, IA real, autenticação, conectores, deploy, testes e documentação. Para fechar com excelência, a estratégia deve ser reduzir risco, tornar a experiência mais intuitiva e mostrar valor com um fluxo de demonstração simples: subir documentos, preparar a base, perguntar, gerar análise, auditar fontes e exportar evidências.
