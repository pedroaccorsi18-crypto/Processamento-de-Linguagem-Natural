# Arquitetura do Synapse AI

## Visão arquitetural

Synapse AI usa Streamlit como camada de interface e organiza o código em módulos testáveis dentro de `src/synapse_ai`. A Fase 3 inicial adiciona chunking, embeddings, busca semântica e respostas com rastreabilidade.

## Responsabilidades dos diretórios

- `auth`: autenticação Supabase Auth, sessão local do Streamlit e guards.
- `clients`: inicialização controlada dos clientes Supabase e OpenAI.
- `models`: modelos simples de usuário, documento e análise.
- `services`: parsing, extração, persistência, chunking, embeddings, busca semântica e geração RAG.
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
- `openai.embedding_model` opcional
- `openai.generation_model` opcional
- `openai.transcription_model` opcional
- `google_drive.client_id` opcional
- `google_drive.client_secret` opcional
- `google_drive.redirect_uri` opcional
- `google_drive.api_key` opcional para demonstrações

## Fluxo de autenticação

As páginas de login e cadastro chamam funções de `auth/auth.py`, que encapsulam Supabase Auth. O módulo normaliza respostas e erros para a interface, sem registrar senhas, tokens ou detalhes sensíveis.

## Fluxo de sessão

`auth/session.py` concentra o uso de `st.session_state`. Ele guarda estado autenticado, usuário atual, access token e refresh token. As demais camadas usam funções pequenas em vez de acessar `st.session_state` diretamente.

## Streamlit e Supabase

Streamlit renderiza a interface e recebe ações do usuário. Supabase Auth gerencia cadastro, login e logout. O cliente Supabase é criado com URL do projeto e publishable key, sem service role, senha de banco ou JWT secret.

## Relação com OpenAI

O cliente OpenAI é o ponto central de inicialização e não executa chamadas no import nem na inicialização do app. As chamadas reais ficam em serviços explícitos: `embedding_service.py` gera embeddings e `analysis_service.py` gera respostas com contexto recuperado.

## Isolamento por camadas

`app.py` coordena configuração, sessão e navegação. Regras de autenticação ficam em `auth`, clientes externos em `clients`, lógica de negócio em `services`, dados em `models` e telas em `ui`.

## Estratégia para documentos

`document_service.py` valida uploads, extrai texto de PDF, DOCX, PPTX, XLSX, TXT, MD, CSV, JSON,
VTT e EML, normaliza conteúdo e gera metadados. Arquivos de áudio passam por transcrição automática
antes de serem salvos como texto pesquisável. Exportações de tickets/Jira em CSV ou XLSX são
detectadas por cabeçalhos típicos e convertidas em registros textuais estruturados antes da indexação
semântica. Exportações de Slack em JSON e mensagens/transcrições de Microsoft Teams em JSON ou VTT
também são convertidas em registros textuais com autor, data/hora, plataforma e contagem de mensagens.
O Google Drive usa OAuth como caminho recomendado de produto: o usuário autoriza o Synapse AI com
escopo somente leitura e a sessão usa `Authorization: Bearer` para chamadas à Drive API v3. Arquivos
comuns são baixados por `files.get` com `alt=media`, enquanto Google Docs, Sheets e Slides são
exportados por `files.export` para DOCX, XLSX e PPTX antes de entrar no mesmo pipeline documental.
A API key permanece apenas como compatibilidade de demonstração para pastas compartilhadas.
`document_repository.py` persiste o registro na tabela `documents` com `user_id`, texto extraído,
contagem de caracteres e metadados. `document_storage.py` armazena o arquivo original em bucket
privado para download futuro pelo próprio usuário.

## Estratégia para RAG

Na Fase 3 inicial, `chunking_service.py` divide o texto extraído em trechos, `embedding_service.py` gera vetores, `chunk_repository.py` persiste esses trechos em `document_chunks` e chama funções SQL de busca semântica. A interface permite selecionar explicitamente quais documentos compõem o escopo da pergunta. A geração preserva rastreabilidade por meio dos trechos recuperados e apresentados como fontes.

## Estratégia para inteligência organizacional

Na Fase 4 inicial, `intelligence_service.py` transforma trechos recuperados em achados estruturados, como decisões, riscos, inconsistências, pendências, prazos, responsáveis e recomendações. Esses achados são salvos na tabela `analyses` como artefatos tipados em `metadata.artifact_type = "intelligence_snapshot"`, preservando o histórico e evitando uma nova dependência de schema nesta etapa.

`comparison_service.py` usa a mesma base semântica para comparar documentos selecionados e detectar divergências de cronograma, responsabilidade, decisão, risco, escopo e evidência. O resultado é salvo como `metadata.artifact_type = "document_comparison"` e pode ser exportado em Excel, CSV e Markdown.

`sentiment_service.py` adiciona uma camada explícita de Análise de Sentimentos aplicada ao contexto organizacional. O serviço identifica sinais de urgência, tensão, confiança, alinhamento, conflito, frustração e risco percebido, sempre com fontes e sem inferir traços psicológicos individuais. O resultado é salvo como `metadata.artifact_type = "sentiment_report"` e pode ser exportado em Excel, CSV e Markdown.

`alert_service.py` transforma evidências recuperadas em alertas preventivos, priorizando sinais como prazo crítico, responsável ausente, decisão conflitante, aprovação pendente, dependência externa e lacuna de evidência. O resultado é salvo como `metadata.artifact_type = "preventive_alert_report"` e aparece no Dashboard como radar executivo de acompanhamento.

`pattern_service.py` usa os artefatos salvos em `analyses.metadata` como memória institucional para reconhecer recorrências. Ele compara sinais atuais recuperados via RAG com achados, alertas, sentimentos, comparações e planos salvos anteriormente, permitindo identificar padrões como atraso por aprovação financeira, tensão comunicacional recorrente ou lacunas repetidas de responsabilidade. O resultado é salvo como `metadata.artifact_type = "historical_pattern_report"`.

`agent_service.py` implementa agentes especializados reais. Cada agente executa uma chamada independente ao modelo com missão e contrato de saída próprios: decisões, riscos, consistência documental, sentimentos e governança. Depois, um orquestrador consolida os pareceres em consensos, conflitos, lacunas e recomendações, sem criar fatos novos fora dos achados dos agentes. O resultado é salvo como `metadata.artifact_type = "multi_agent_report"`.

O mesmo mecanismo de fontes alimenta a auditoria, permitindo que cada achado ou divergência seja revisado junto dos documentos, trechos e níveis de similaridade que sustentaram a análise.

## Decisões de segurança

- Segredos reais ficam apenas em `.streamlit/secrets.toml`.
- `.streamlit/secrets.toml` é ignorado pelo Git.
- Não há credenciais no código, documentação ou testes.
- Logs registram classes de erro, não valores sensíveis.
- O SQL habilita Row Level Security nas entidades privadas.
- Cada usuário acessa apenas seus próprios documentos e análises.
- Arquivos originais ficam em bucket privado e em uma pasta derivada do `user_id`.
- Arquivos enviados são processados em memória na etapa de upload.
- Documentos só são enviados à OpenAI quando o usuário prepara a base semântica, faz perguntas, gera planos, extrai inteligência estruturada ou cria relatórios executivos.
- O histórico de perguntas, respostas, planos de ação e inteligência estruturada é opcional; por padrão, a análise é exibida sem persistir a interação.
- As fontes salvas no histórico guardam metadados de rastreabilidade, não uma cópia integral dos trechos recuperados.

## Limitações atuais

- O schema é entregue para execução manual, não automática.
- A busca vetorial depende da extensão `pgvector` habilitada no Supabase.
- Ainda não há conectores privados com OAuth para Teams, Slack, Jira, SharePoint, CRM ou ERP além do Google Drive.
- Não há versionamento avançado de documentos.

## Próximos passos

Evoluir a Fase 4 com alertas preventivos, avaliação de qualidade das respostas e, depois, uma integração MCP para expor o Synapse AI como ferramenta consultável.
