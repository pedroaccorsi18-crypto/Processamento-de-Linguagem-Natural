# Publicação web do Synapse AI

Este documento descreve o caminho recomendado para tirar o Synapse AI do `localhost` e deixá-lo
acessível por uma URL pública para apresentação.

## Estratégia recomendada

Para a entrega acadêmica, a opção mais simples é publicar o app Streamlit em um serviço gerenciado,
mantendo o Supabase como backend remoto e a OpenAI como provedor de IA.

URL pública configurada para apresentação:

```text
https://synapse-ai-pnl.streamlit.app/
```

Ordem recomendada:

1. GitHub com o repositório atualizado.
2. Streamlit Community Cloud como primeira opção de deploy.
3. Render, Railway ou outro serviço Python como alternativa.
4. Supabase remoto já configurado com `supabase/schema.sql`.
5. Google Cloud OAuth apontando para a URL pública final.

## Arquivos necessários para deploy

- `app.py`: ponto de entrada do Streamlit.
- `requirements.txt`: instala o pacote local e suas dependências.
- `pyproject.toml`: declara as dependências de runtime e desenvolvimento.
- `runtime.txt`: fixa Python 3.11.
- `.streamlit/config.toml`: configuração segura do Streamlit.
- `.streamlit/secrets.example.toml`: modelo de segredos, sem credenciais reais.

## Segredos necessários no ambiente web

Configure no painel do serviço de deploy os mesmos blocos abaixo, substituindo apenas os valores:

```toml
[supabase]
url = "https://SEU-PROJETO.supabase.co"
publishable_key = "SUA_SUPABASE_PUBLISHABLE_KEY"

[openai]
api_key = "SUA_OPENAI_API_KEY"
embedding_model = "text-embedding-3-small"
generation_model = "gpt-5-mini"
transcription_model = "gpt-4o-mini-transcribe"

[app]
public_url = "https://SUA-URL-PUBLICA"

[google_drive]
api_key = ""
client_id = "SEU_GOOGLE_OAUTH_CLIENT_ID"
client_secret = "SEU_GOOGLE_OAUTH_CLIENT_SECRET"
redirect_uri = "https://SUA-URL-PUBLICA"
```

Nunca publique `.streamlit/secrets.toml` no GitHub.

## Google OAuth

Quando a URL pública existir, atualize o cliente OAuth no Google Cloud:

1. Abra o projeto Google Cloud usado pelo Synapse AI.
2. Entre em Google Auth Platform.
3. Abra o cliente OAuth Web do Synapse AI.
4. Adicione a URL pública do app em URIs de redirecionamento autorizados.
5. Atualize `google_drive.redirect_uri` nos segredos do deploy com a mesma URL.
6. Teste o botão de conexão do Google Drive já no endereço público.

Se o redirect URI do Google Cloud e o valor em `secrets` forem diferentes, o Google recusará o login.

## Supabase

Antes do deploy:

1. Confirme que `supabase/schema.sql` foi executado no projeto correto.
2. Em Authentication > URL Configuration, configure Site URL com a URL pública do app.
3. Em Redirect URLs, adicione a URL pública do app.
4. Confirme que o bucket privado `documents` existe.
5. Confirme que Row Level Security está ativa.
6. Confirme que e-mail/senha está habilitado em Supabase Auth.
7. Teste login, cadastro, upload e download com um usuário de demonstração.

## Checklist de validação pós-deploy

Execute estes testes na URL pública:

1. Abrir a página inicial.
2. Criar ou acessar usuário de demonstração.
3. Fazer upload de PDF.
4. Fazer upload de CSV/XLSX de tickets.
5. Fazer upload de JSON Slack ou Teams.
6. Fazer upload de VTT de transcrição.
7. Conectar Google Drive.
8. Importar arquivo de uma pasta do Google Drive.
9. Preparar base semântica.
10. Fazer pergunta com fontes.
11. Gerar plano de ação.
12. Gerar inteligência organizacional.
13. Gerar alertas preventivos.
14. Gerar padrões históricos.
15. Gerar relatório executivo.
16. Abrir auditoria e baixar pacote de evidências.

## Plano de contingência para apresentação

Se o serviço web falhar no dia:

1. manter o app rodando localmente;
2. abrir pelo navegador com `http://localhost:8501`;
3. usar dados já carregados no Supabase;
4. ter PDFs e planilhas de teste preparados;
5. ter prints curtos das principais telas como evidência de backup.
