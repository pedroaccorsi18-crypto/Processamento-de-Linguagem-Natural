export type DashboardStats = {
  base_ready: number;
  evidence_count: number;
  risk_count: number;
  pending_confirmation_count: number;
};

export type SynapseDocument = {
  id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number | null;
  status: string;
  text_char_count: number;
  metadata: Record<string, unknown>;
  created_at: string | null;
  original_file_available: boolean;
};

export type CopilotMessagePayload = {
  role: "user" | "assistant";
  content: string;
};

export type StudioWorkflow =
  | "ask"
  | "action_plan"
  | "intelligence_snapshot"
  | "document_comparison"
  | "sentiment_analysis"
  | "preventive_alerts"
  | "historical_patterns"
  | "multi_agent";

export type StudioDocument = SynapseDocument & {
  prepared_for_ai: boolean;
  indexed_chunk_count: number;
};

export type StudioPreparationResponse = {
  indexed_chunks: number;
  message: string;
};

export type StudioAnalysisResponse = {
  workflow: StudioWorkflow;
  message: string;
  saved_to_history: boolean;
  persistence_warning: string | null;
  result: Record<string, unknown>;
};

export type StudioHistoryEntry = {
  id: string;
  title: string;
  question: string;
  answer: string;
  sources: Record<string, unknown>[];
  model: string | null;
  status: string;
  metadata: Record<string, unknown>;
  document_filename: string | null;
  created_at: string | null;
};

export type IntegrationProvider = "google_drive" | "slack" | "microsoft_teams" | "sharepoint";

export type IntegrationStatus = {
  provider: IntegrationProvider;
  label: string;
  availability: "available" | "needs_configuration" | "coming_soon";
  connected: boolean;
  connected_at: string | null;
  detail: string;
};

export type GoogleDriveFile = {
  id: string;
  name: string;
  mime_type: string;
  size_bytes: number | null;
  web_view_link: string | null;
};

export type GoogleDriveImportResponse = {
  imported_documents: SynapseDocument[];
  failures: Array<{ filename: string; detail: string }>;
  message: string;
};

export type OAuthAuthorization = {
  authorization_url: string;
  state: string;
};

export type ConnectorImportResponse = {
  imported_documents: SynapseDocument[];
  failures: Array<{ filename: string; detail: string }>;
  message: string;
};

export type SlackConversation = {
  id: string;
  name: string;
  is_private: boolean;
  topic: string;
};

export type MicrosoftTeam = {
  id: string;
  name: string;
  description: string;
};

export type MicrosoftChannel = {
  id: string;
  name: string;
  description: string;
};

export type SharePointSite = {
  id: string;
  name: string;
  web_url: string;
};

export type SharePointDrive = {
  id: string;
  name: string;
  web_url: string;
};

export type SharePointFile = {
  id: string;
  name: string;
  mime_type: string;
  size_bytes: number | null;
  web_url: string;
  is_folder: boolean;
};

type CopilotResponse = {
  answer: string;
  model: string;
};

type DocumentUploadResponse = {
  document: SynapseDocument;
  message: string;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL;
const REQUEST_TIMEOUT_MS = 12_000;
const COPILOT_REQUEST_TIMEOUT_MS = 75_000;
const STUDIO_PREPARATION_TIMEOUT_MS = 90_000;
const STUDIO_ANALYSIS_TIMEOUT_MS = 150_000;
const CONNECTOR_REQUEST_TIMEOUT_MS = 90_000;

function apiEndpoint(path: string): string {
  if (!apiUrl) {
    throw new Error("A conexão com a API ainda não foi configurada.");
  }

  return `${apiUrl.replace(/\/$/, "")}${path}`;
}

async function fetchApi(
  path: string,
  accessToken: string,
  init?: RequestInit,
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);

  try {
    const response = await fetch(apiEndpoint(path), {
      ...init,
      headers,
      signal: controller.signal,
    });
    if (response.status === 401) {
      throw new Error("Sua sessão expirou. Entre novamente para continuar.");
    }
    return response;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("A API demorou mais do que o esperado. Tente novamente em instantes.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function responseError(response: Response, fallback: string): Promise<Error> {
  const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  if (typeof payload?.detail === "string") {
    return new Error(payload.detail);
  }
  if (Array.isArray(payload?.detail) && payload.detail.length > 0) {
    return new Error(fallback);
  }
  return new Error(fallback);
}

export async function getDashboardStats(accessToken: string): Promise<DashboardStats> {
  const response = await fetchApi("/api/dashboard/stats", accessToken, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw await responseError(response, "Não foi possível carregar os indicadores do painel.");
  }
  return (await response.json()) as DashboardStats;
}

export async function listDocuments(accessToken: string): Promise<SynapseDocument[]> {
  const response = await fetchApi("/api/documents", accessToken, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw await responseError(response, "Não foi possível carregar os documentos.");
  }
  return (await response.json()) as SynapseDocument[];
}

export async function uploadDocument(
  accessToken: string,
  file: File,
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetchApi("/api/documents", accessToken, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw await responseError(response, "Não foi possível processar o documento.");
  }
  return (await response.json()) as DocumentUploadResponse;
}

export async function downloadDocument(accessToken: string, document: SynapseDocument): Promise<void> {
  const response = await fetchApi(`/api/documents/${document.id}/download`, accessToken);
  if (!response.ok) {
    throw await responseError(response, "Não foi possível baixar o arquivo original.");
  }

  const url = URL.createObjectURL(await response.blob());
  const anchor = window.document.createElement("a");
  anchor.href = url;
  anchor.download = document.filename;
  window.document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function askCopilot(input: {
  accessToken: string;
  messages: CopilotMessagePayload[];
  currentArea: string;
  currentPath?: string;
  documentId?: string | null;
  documentIds?: string[];
  context: string;
}): Promise<CopilotResponse> {
  const response = await fetchApi("/api/copilot", input.accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: input.messages.slice(-12),
      current_area: input.currentArea,
      current_path: input.currentPath,
      document_id: input.documentId,
      document_ids: input.documentIds ?? [],
      context: input.context,
    }),
  }, COPILOT_REQUEST_TIMEOUT_MS);
  if (!response.ok) {
    throw await responseError(response, "Não foi possível consultar o Copiloto agora.");
  }
  return (await response.json()) as CopilotResponse;
}

export async function listStudioDocuments(accessToken: string): Promise<StudioDocument[]> {
  const response = await fetchApi("/api/studio/documents", accessToken, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw await responseError(response, "Não foi possível carregar o escopo documental.");
  }
  return (await response.json()) as StudioDocument[];
}

export async function prepareStudioDocuments(input: {
  accessToken: string;
  selectedDocumentIds: string[];
}): Promise<StudioPreparationResponse> {
  const response = await fetchApi(
    "/api/studio/prepare",
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected_document_ids: input.selectedDocumentIds }),
    },
    STUDIO_PREPARATION_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível preparar este escopo para IA.");
  }
  return (await response.json()) as StudioPreparationResponse;
}

export async function runStudioAnalysis(input: {
  accessToken: string;
  workflow: StudioWorkflow;
  selectedDocumentIds: string[];
  question?: string;
  saveToHistory: boolean;
}): Promise<StudioAnalysisResponse> {
  const response = await fetchApi(
    `/api/studio/analyses/${input.workflow}`,
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selected_document_ids: input.selectedDocumentIds,
        question: input.question,
        save_to_history: input.saveToHistory,
      }),
    },
    STUDIO_ANALYSIS_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível concluir a análise agora.");
  }
  return (await response.json()) as StudioAnalysisResponse;
}

export async function listStudioHistory(
  accessToken: string,
  limit = 20,
): Promise<StudioHistoryEntry[]> {
  const response = await fetchApi(
    `/api/studio/history?limit=${encodeURIComponent(String(limit))}`,
    accessToken,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível carregar o histórico do Estúdio.");
  }
  return (await response.json()) as StudioHistoryEntry[];
}

export async function listIntegrations(accessToken: string): Promise<IntegrationStatus[]> {
  const response = await fetchApi("/api/integrations", accessToken, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw await responseError(response, "Não foi possível carregar as fontes corporativas.");
  }
  return (await response.json()) as IntegrationStatus[];
}

export async function beginGoogleDriveAuthorization(accessToken: string): Promise<{
  authorization_url: string;
  state: string;
  code_verifier: string;
}> {
  const response = await fetchApi(
    "/api/integrations/google-drive/authorization",
    accessToken,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível iniciar a conexão com o Google Drive.");
  }
  return (await response.json()) as {
    authorization_url: string;
    state: string;
    code_verifier: string;
  };
}

export async function completeGoogleDriveAuthorization(input: {
  accessToken: string;
  code: string;
  state: string;
  codeVerifier: string;
}): Promise<IntegrationStatus> {
  const response = await fetchApi(
    "/api/integrations/google-drive/complete",
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code: input.code,
        state: input.state,
        code_verifier: input.codeVerifier,
      }),
    },
    CONNECTOR_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível concluir a conexão com o Google Drive.");
  }
  return (await response.json()) as IntegrationStatus;
}

export async function disconnectGoogleDrive(accessToken: string): Promise<void> {
  const response = await fetchApi("/api/integrations/google-drive", accessToken, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, "Não foi possível desconectar o Google Drive.");
  }
}

export async function listGoogleDriveFiles(input: {
  accessToken: string;
  folderReference: string;
}): Promise<GoogleDriveFile[]> {
  const response = await fetchApi(
    "/api/integrations/google-drive/files",
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder_reference: input.folderReference }),
    },
    CONNECTOR_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível listar os arquivos do Google Drive.");
  }
  return (await response.json()) as GoogleDriveFile[];
}

export async function importGoogleDriveFiles(input: {
  accessToken: string;
  folderReference: string;
  fileIds: string[];
}): Promise<GoogleDriveImportResponse> {
  const response = await fetchApi(
    "/api/integrations/google-drive/import",
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        folder_reference: input.folderReference,
        file_ids: input.fileIds,
      }),
    },
    CONNECTOR_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível importar os arquivos do Google Drive.");
  }
  return (await response.json()) as GoogleDriveImportResponse;
}

export async function beginSlackAuthorization(accessToken: string): Promise<OAuthAuthorization> {
  const response = await fetchApi(
    "/api/integrations/slack/authorization",
    accessToken,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível iniciar a conexão com o Slack.");
  }
  return (await response.json()) as OAuthAuthorization;
}

export async function completeSlackAuthorization(input: {
  accessToken: string;
  code: string;
  state: string;
}): Promise<IntegrationStatus> {
  return completeConnectorAuthorization("slack", input, "Slack");
}

export async function disconnectSlack(accessToken: string): Promise<void> {
  return disconnectConnector("slack", accessToken, "Slack");
}

export async function listSlackConversations(accessToken: string): Promise<SlackConversation[]> {
  const response = await fetchApi("/api/integrations/slack/conversations", accessToken, {
    headers: { Accept: "application/json" },
  }, CONNECTOR_REQUEST_TIMEOUT_MS);
  if (!response.ok) {
    throw await responseError(response, "Não foi possível listar os canais do Slack.");
  }
  return (await response.json()) as SlackConversation[];
}

export async function importSlackConversations(input: {
  accessToken: string;
  conversationIds: string[];
  messageLimit?: number;
}): Promise<ConnectorImportResponse> {
  const response = await fetchApi(
    "/api/integrations/slack/import",
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_ids: input.conversationIds,
        message_limit: input.messageLimit ?? 100,
      }),
    },
    CONNECTOR_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível importar os canais do Slack.");
  }
  return (await response.json()) as ConnectorImportResponse;
}

export async function beginMicrosoftAuthorization(
  accessToken: string,
): Promise<OAuthAuthorization> {
  const response = await fetchApi(
    "/api/integrations/microsoft/authorization",
    accessToken,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível iniciar a conexão Microsoft 365.");
  }
  return (await response.json()) as OAuthAuthorization;
}

export async function completeMicrosoftAuthorization(input: {
  accessToken: string;
  code: string;
  state: string;
}): Promise<IntegrationStatus> {
  return completeConnectorAuthorization("microsoft", input, "Microsoft 365");
}

export async function disconnectMicrosoft(accessToken: string): Promise<void> {
  return disconnectConnector("microsoft", accessToken, "Microsoft 365");
}

export async function listMicrosoftTeams(accessToken: string): Promise<MicrosoftTeam[]> {
  const response = await fetchApi("/api/integrations/microsoft/teams", accessToken, {
    headers: { Accept: "application/json" },
  }, CONNECTOR_REQUEST_TIMEOUT_MS);
  if (!response.ok) {
    throw await responseError(response, "Não foi possível listar as equipes do Microsoft Teams.");
  }
  return (await response.json()) as MicrosoftTeam[];
}

export async function listMicrosoftTeamChannels(input: {
  accessToken: string;
  teamId: string;
}): Promise<MicrosoftChannel[]> {
  const response = await fetchApi(
    "/api/integrations/microsoft/teams/channels",
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team_id: input.teamId }),
    },
    CONNECTOR_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível listar os canais desta equipe.");
  }
  return (await response.json()) as MicrosoftChannel[];
}

export async function importMicrosoftTeamChannels(input: {
  accessToken: string;
  teamId: string;
  channels: MicrosoftChannel[];
  messageLimit?: number;
}): Promise<ConnectorImportResponse> {
  const response = await fetchApi(
    "/api/integrations/microsoft/teams/import",
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        team_id: input.teamId,
        channels: input.channels,
        message_limit: input.messageLimit ?? 100,
      }),
    },
    CONNECTOR_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível importar os canais do Microsoft Teams.");
  }
  return (await response.json()) as ConnectorImportResponse;
}

export async function listSharePointSites(accessToken: string): Promise<SharePointSite[]> {
  const response = await fetchApi(
    "/api/integrations/microsoft/sharepoint/sites",
    accessToken,
    { headers: { Accept: "application/json" } },
    CONNECTOR_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível listar os sites do SharePoint.");
  }
  return (await response.json()) as SharePointSite[];
}

export async function listSharePointDrives(input: {
  accessToken: string;
  siteId: string;
}): Promise<SharePointDrive[]> {
  const response = await fetchApi(
    "/api/integrations/microsoft/sharepoint/drives",
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ site_id: input.siteId }),
    },
    CONNECTOR_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível listar as bibliotecas do SharePoint.");
  }
  return (await response.json()) as SharePointDrive[];
}

export async function listSharePointFiles(input: {
  accessToken: string;
  driveId: string;
  folderId?: string;
}): Promise<SharePointFile[]> {
  const response = await fetchApi(
    "/api/integrations/microsoft/sharepoint/files",
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drive_id: input.driveId, folder_id: input.folderId ?? "" }),
    },
    CONNECTOR_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível listar os arquivos do SharePoint.");
  }
  return (await response.json()) as SharePointFile[];
}

export async function importSharePointFiles(input: {
  accessToken: string;
  driveId: string;
  files: SharePointFile[];
}): Promise<ConnectorImportResponse> {
  const response = await fetchApi(
    "/api/integrations/microsoft/sharepoint/import",
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drive_id: input.driveId, files: input.files }),
    },
    CONNECTOR_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, "Não foi possível importar os arquivos do SharePoint.");
  }
  return (await response.json()) as ConnectorImportResponse;
}

async function completeConnectorAuthorization(
  provider: "slack" | "microsoft",
  input: { accessToken: string; code: string; state: string },
  label: string,
): Promise<IntegrationStatus> {
  const response = await fetchApi(
    `/api/integrations/${provider}/complete`,
    input.accessToken,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: input.code, state: input.state }),
    },
    CONNECTOR_REQUEST_TIMEOUT_MS,
  );
  if (!response.ok) {
    throw await responseError(response, `Não foi possível concluir a conexão ${label}.`);
  }
  return (await response.json()) as IntegrationStatus;
}

async function disconnectConnector(
  provider: "slack" | "microsoft",
  accessToken: string,
  label: string,
): Promise<void> {
  const response = await fetchApi(`/api/integrations/${provider}`, accessToken, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw await responseError(response, `Não foi possível desconectar ${label}.`);
  }
}
