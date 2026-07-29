# Synapse AI Frontend

Esqueleto Next.js com TypeScript, App Router e TailwindCSS para a migração SaaS B2B do Synapse AI.

## Rodar localmente

1. Inicie a API FastAPI na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

2. Inicie o frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

3. Abra `http://localhost:3000`.

## Integração com a API

O componente `CopilotChat` chama `POST /api/copilot`. Em produção, configure `NEXT_PUBLIC_API_BASE_URL` para o endereço público do backend.
