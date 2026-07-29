# Operação em produção

## Manter a API ativa

O workflow `Keep Synapse API Awake` consulta a rota de saúde da API do Synapse AI a cada cinco minutos. A URL pública não é segredo e está versionada em `.github/workflows/keep-render-awake.yml`.

## Alertas por e-mail

Quando a verificação falha, o workflow tenta enviar um e-mail usando SMTP. Configure estes GitHub Secrets uma única vez; nenhum valor deve ser versionado:

- `SYNAPSE_ALERT_SMTP_SERVER`
- `SYNAPSE_ALERT_SMTP_PORT`
- `SYNAPSE_ALERT_SMTP_USERNAME`
- `SYNAPSE_ALERT_SMTP_PASSWORD`
- `SYNAPSE_ALERT_EMAIL`

Caso os Secrets ainda não estejam configurados, a falha continua registrada no GitHub Actions. O passo de e-mail não altera o resultado do monitoramento.

## Homologação E2E local

O arquivo `frontend/.env.e2e` é ignorado pelo Git e contém exclusivamente as configurações locais da suíte Playwright. A chave administrativa do Supabase usada para criar e remover contas de teste não deve ser colocada na Vercel, no Render ou em arquivos versionados.
