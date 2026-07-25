# Arquitetura do Synapse AI

## Visão arquitetural

Synapse AI usa Streamlit como camada de interface e organiza o código em módulos testáveis dentro de `src/synapse_ai`. A Fase 2 adiciona upload, extração textual local, metadados e persistência inicial de documentos.

## Responsabilidades dos diretórios

- `auth`: autenticação Supabase Auth, sessão local do Streamlit e guards.
- `clients`: inicialização controlada dos clientes Supabase e OpenAI.
- `models`: modelos simples de usuário, documento e análise.
- `services`: parsing, extração, persistência inicial de documentos e contratos de análises.
- `ui`: páginas e navegação Streamlit.
- `utils`: logging e validações compartilhadas.
- `tests`: testes unitários e smoke tests sem serviços reais.
- `supabase`: SQL revisável para execução manual.

## Fluxo de configuração

`config.py` é o único módulo que lê `st.secrets`. Ele valida as chaves esperadas e retorna objetos tipados. Os valores sensíveis não aparecem em `repr`, logs, README ou testes.

Configuração esperada:

- `supabase.url`
- `supabase.publishable_key`
- `openai.api_key`

## Fluxo de autenticação

As páginas de login e cadastro chamam funções de `auth/auth.py`, que encapsulam Supabase Auth. O módulo normaliza respostas e erros para a interface, sem registrar senhas, tokens ou detalhes sensíveis.

## Fluxo de sessão

`auth/session.py` concentra o uso de `st.session_state`. Ele guarda estado autenticado, usuário atual, access token e refresh token. As demais camadas usam funções pequenas em vez de acessar `st.session_state` diretamente.

## Streamlit e Supabase

Streamlit renderiza a interface e recebe ações do usuário. Supabase Auth gerencia cadastro, login e logout. O cliente Supabase é criado com URL do projeto e publishable key, sem service role, senha de banco ou JWT secret.

## Relação futura com OpenAI

O cliente OpenAI já existe como ponto central de inicialização, mas não executa chamadas no import nem na inicialização do app. Fases futuras devem usar serviços explícitos para chunking, embeddings, busca semântica e geração.

## Isolamento por camadas

`app.py` coordena configuração, sessão e navegação. Regras de autenticação ficam em `auth`, clientes externos em `clients`, lógica de negócio em `services`, dados em `models` e telas em `ui`.

## Estratégia para documentos

`document_service.py` valida uploads, extrai texto de PDF, DOCX, TXT e MD, normaliza conteúdo e gera metadados. `document_repository.py` persiste o registro na tabela `documents` com `user_id`, texto extraído, contagem de caracteres e metadados.

## Estratégia futura para RAG

Na Fase 3, o projeto deve adicionar chunking, embeddings, banco vetorial e recuperação semântica. A geração deve preservar rastreabilidade dos trechos usados.

## Decisões de segurança

- Segredos reais ficam apenas em `.streamlit/secrets.toml`.
- `.streamlit/secrets.toml` é ignorado pelo Git.
- Não há credenciais no código, documentação ou testes.
- Logs registram classes de erro, não valores sensíveis.
- O SQL habilita Row Level Security nas entidades privadas.
- Cada usuário acessa apenas seus próprios documentos e análises.
- Arquivos enviados são processados em memória nesta fase.
- Nenhum documento é enviado à OpenAI na Fase 2.

## Limitações da Fase 2

- Análises automáticas não executam IA.
- Não existe banco vetorial.
- Não existe RAG.
- O schema é entregue para execução manual, não automática.
- Não há chunking semântico.
- Não há versionamento avançado de documentos.

## Próximos passos

Na Fase 3, implementar chunking, embeddings, banco vetorial, busca semântica e RAG com rastreabilidade das fontes.
