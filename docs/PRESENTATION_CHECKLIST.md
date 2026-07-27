# Roteiro de apresentação do Synapse AI

## Objetivo da demonstração

Mostrar que o Synapse AI transforma documentos organizacionais dispersos em inteligência consultável,
com busca semântica, respostas com fontes, planos de ação, alertas, padrões históricos e auditoria.

## Narrativa recomendada

1. Organizações perdem decisões, riscos e responsáveis em arquivos espalhados.
2. O Synapse AI centraliza documentos e fontes corporativas.
3. O sistema extrai texto, preserva o arquivo original e cria uma base semântica.
4. O usuário faz perguntas em linguagem natural.
5. A resposta vem com fontes rastreáveis.
6. A plataforma também gera artefatos executivos: plano de ação, alertas, padrões e relatórios.
7. A auditoria permite revisar de onde cada resposta saiu.

## Demonstração principal

### 1. Login

- Entrar com usuário de demonstração.
- Mostrar que a área autenticada separa Dashboard, Upload, Análises e Auditoria.

### 2. Upload

Subir pelo menos três tipos de documento:

- PDF institucional.
- CSV ou XLSX de tickets/Jira.
- JSON de Slack ou Teams, ou VTT de transcrição.

Mensagem-chave:

> O Synapse não depende de um único formato. Ele aceita documentos, planilhas, e-mails, áudios,
> transcrições e exportações de plataformas corporativas.

### 3. Google Drive

- Conectar Google Drive.
- Buscar arquivos por link ou ID de pasta compartilhada.
- Importar um arquivo.

Mensagem-chave:

> Para produto real, já temos OAuth com Google Drive. Para outras plataformas, o MVP aceita
> exportações organizacionais reais, o que é adequado para uma entrega segura e demonstrável.

### 4. Preparar base semântica

- Selecionar documentos.
- Atualizar a base semântica.
- Explicar que essa etapa gera embeddings e trechos pesquisáveis.

Mensagem-chave:

> Esta etapa indexa os documentos para que as perguntas possam usar busca semântica.

### 5. Pergunta com fontes

Pergunta sugerida:

> Quais decisões, riscos e responsáveis aparecem nos documentos selecionados?

Mostrar:

- síntese;
- fontes;
- documentos usados;
- trechos recuperados.

### 6. Plano de ação

Gerar plano de ação e destacar:

- tarefa;
- responsável;
- prazo;
- evidência;
- recomendação.

### 7. Inteligência organizacional

Gerar snapshot ou relatório de inteligência e destacar:

- decisões;
- riscos;
- pendências;
- inconsistências;
- lacunas de evidência.

### 8. Alertas preventivos

Mostrar alertas e explicar:

> A plataforma não apenas responde perguntas. Ela antecipa riscos a partir de sinais recorrentes nos
> documentos.

### 9. Padrões históricos

Mostrar padrões históricos se houver análises salvas.

Mensagem-chave:

> O histórico permite perceber recorrências, como atraso por aprovação financeira ou ausência de
> responsáveis.

### 10. Auditoria

- Abrir a trilha de evidências.
- Mostrar fontes e documentos relacionados.
- Baixar pacote de evidências.

Mensagem-chave:

> A IA não fica como caixa-preta. Cada resposta pode ser revisada com fonte e evidência.

## Perguntas prováveis da banca

### O sistema toma decisões sozinho?

Resposta recomendada:

> Não. Ele apoia decisão. O sistema identifica evidências, riscos, responsáveis e recomendações, mas
> a decisão final permanece com o colaborador ou gestor.

### O sistema acessa dados privados dos usuários?

Resposta recomendada:

> O projeto usa autenticação, Row Level Security no Supabase e bucket privado. Cada usuário acessa
> seus próprios documentos. O histórico de análises é controlado e auditável.

### Por que nem todos os conectores são OAuth nativos?

Resposta recomendada:

> Porque o escopo acadêmico priorizou um MVP funcional e seguro. O Google Drive já está integrado por
> OAuth. Slack, Teams, Jira e outros sistemas entram por exportações reais, que são comuns em ambientes
> corporativos e preservam o mesmo pipeline de inteligência.

### Qual é o diferencial técnico?

Resposta recomendada:

> O diferencial é combinar RAG, busca vetorial, rastreabilidade de fontes, memória histórica,
> relatórios executivos e arquitetura modular com camada Application e casos de uso testáveis.

## Checklist final antes da apresentação

- App publicado em URL pública.
- Google OAuth configurado para a URL pública.
- Supabase remoto funcionando.
- OpenAI com créditos disponíveis.
- Usuário de demonstração criado.
- Documentos de teste preparados.
- Base semântica já preparada para pelo menos um conjunto.
- Histórico com algumas análises salvas.
- Relatório executivo gerado.
- Pacote de evidências baixável.
- Plano B local funcionando.
