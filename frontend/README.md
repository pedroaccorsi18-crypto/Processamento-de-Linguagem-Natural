# Synapse AI Frontend

Frontend Next.js com TypeScript, App Router e TailwindCSS para a migração SaaS B2B do Synapse AI.

## Rodar localmente

1. Prepare as variáveis do backend e inicie a API FastAPI na raiz do projeto:

```powershell
Copy-Item backend\.env.example backend\.env
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --env-file backend\.env --host 127.0.0.1 --port 8000 --reload
```

2. Prepare as variáveis do frontend e inicie o Next.js:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm.cmd install
npm.cmd run dev
```

3. Abra `http://localhost:3000`.

## Configuração de produção

O frontend usa `NEXT_PUBLIC_API_URL` para todas as chamadas ao FastAPI. Na Vercel, configure-a com a URL pública do Render. No Render, configure `CORS_ORIGINS` com a URL pública da Vercel e preencha as demais credenciais exigidas pelo backend.
