# Homologação automatizada

Esta suíte usa Playwright para validar, sem intervenção manual, a interface Next.js e a API FastAPI publicadas. Cada execução cria duas contas temporárias de QA no Supabase, remove-as ao final e nunca utiliza as contas reais da equipe.

## O que a suíte valida

- bloqueio da API sem um token autenticado;
- login de uma conta temporária;
- rejeição imediata de arquivo acima de 10 MB;
- mensagem clara para um formato não suportado;
- upload, persistência, listagem e download do arquivo original;
- isolamento entre duas contas distintas;
- resposta do Copiloto pela API real da OpenAI.

## Configuração local

1. Abra o terminal na pasta `frontend`.
2. Copie o modelo: `Copy-Item .env.e2e.example .env.e2e`.
3. Preencha no arquivo `.env.e2e` as URLs públicas da Vercel e do Render, a URL do Supabase usado por esse ambiente e a chave `service_role` correspondente.
4. Para homologar uma URL externa, altere `ALLOW_EXTERNAL_E2E` para `true`.
5. Execute apenas `npm.cmd run test:e2e`.

O relatório HTML fica em `frontend/playwright-report`. Em caso de falha, capturas, vídeos e trilhas ficam em `frontend/test-results`.

## Regra de segurança

O padrão recomendado é uma pilha de homologação própria: uma Vercel Preview e um Render de teste apontando para um projeto Supabase dedicado. Enquanto essa pilha não existir, a suíte pode validar o ambiente público usando somente usuários QA descartáveis, marcados internamente e removidos ao final. A chave `service_role` nunca deve ser cadastrada na Vercel, no Render ou em qualquer arquivo versionado.

## Execução pelo GitHub Actions

O workflow `Synapse E2E Homologation` foi configurado para execução sob demanda. Cadastre no ambiente GitHub `homologation`:

- variáveis: `SYNAPSE_E2E_BASE_URL`, `SYNAPSE_E2E_API_URL`, `SYNAPSE_E2E_SUPABASE_URL`;
- segredo: `SYNAPSE_E2E_SUPABASE_SERVICE_ROLE_KEY`.

Ele publica relatórios e evidências quando um teste falhar.

# Keep-alive do Render

O workflow `Keep Synapse API Awake` consulta `GET /health` a cada cinco minutos. Configure no GitHub a variável de repositório `SYNAPSE_HEALTHCHECK_URL` com a URL pública completa da API, por exemplo `https://sua-api.onrender.com/health`.

O endpoint retorna `{"status":"ok"}` e não acessa documentos, OpenAI ou Supabase. O agendamento depende da infraestrutura do GitHub e pode atrasar ocasionalmente; ele serve bem para demonstração acadêmica, mas não substitui um plano sem hibernação em produção.
