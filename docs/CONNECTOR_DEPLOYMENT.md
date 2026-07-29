# Conectores corporativos em produção

Este documento registra a configuração operacional dos conectores externos do Synapse AI. Nenhuma credencial deve ser versionada, enviada por e-mail ou exibida na interface.

## Princípios de segurança

- Cada conexão é vinculada ao `user_id` autenticado que autorizou o provedor.
- Tokens OAuth são cifrados no servidor com `CONNECTOR_ENCRYPTION_KEY` antes de serem persistidos.
- O frontend recebe somente o estado da conexão e o conteúdo que o usuário escolheu importar.
- Os conectores são somente leitura. O Synapse AI não publica, edita nem exclui dados nas fontes conectadas.

## Google Drive

O aplicativo OAuth do Google está publicado como externo e em produção. Para a marca aparecer como verificada no consentimento, a organização precisa:

1. Associar um domínio próprio ao frontend publicado.
2. Verificar esse domínio no Google Search Console.
3. Cadastrar no Google Auth Platform as URLs públicas do produto, da Política de Privacidade e dos Termos de Uso.
4. Enviar a verificação de marca quando o Google liberar essa etapa.

URLs públicas previstas pelo frontend:

- `/about`
- `/privacy`
- `/terms`

## Slack

Configure no aplicativo Slack uma Redirect URL igual a `SLACK_REDIRECT_URI` e apenas os escopos de bot abaixo:

- `channels:read`
- `channels:history`
- `groups:read`
- `groups:history`
- `files:read`

Depois de alterar escopos, reinstale o aplicativo no workspace. Adicione o app Synapse AI somente aos canais que deseja importar, inclusive os públicos. Canais privados só aparecem quando o aplicativo também é membro deles; isso é esperado e impede acesso involuntário.

Variáveis do backend:

```text
SLACK_CLIENT_ID=
SLACK_CLIENT_SECRET=
SLACK_REDIRECT_URI=https://<frontend-publico>/upload
```

## Microsoft 365: Teams e SharePoint

Registre um aplicativo no Microsoft Entra ID pertencente a uma organização Microsoft 365. Cadastre uma plataforma Web com redirect URI igual a `MICROSOFT_REDIRECT_URI` e concessão delegada para:

- `offline_access`
- `User.Read`
- `Files.Read.All`
- `Sites.Read.All`
- `Team.ReadBasic.All`
- `ChannelMessage.Read.All`

Um administrador do tenant pode precisar conceder consentimento para as permissões corporativas. Contas Microsoft pessoais não substituem um tenant organizacional do Entra ID para Teams e SharePoint corporativos.

Variáveis do backend:

```text
MICROSOFT_TENANT_ID=<tenant-id-ou-organizations>
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_REDIRECT_URI=https://<frontend-publico>/upload
```

## Variáveis de deploy

No Render, configure as variáveis acima como secretas junto de `CONNECTOR_ENCRYPTION_KEY`. O frontend não recebe client secrets, tokens de provedor ou a chave de cifragem.

Ao mudar uma Redirect URL, atualize o valor no provedor OAuth e no Render na mesma publicação.
