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
): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
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
  return new Error(typeof payload?.detail === "string" ? payload.detail : fallback);
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
  context: string;
}): Promise<CopilotResponse> {
  const response = await fetchApi("/api/copilot", input.accessToken, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: input.messages.slice(-12),
      current_area: input.currentArea,
      context: input.context,
    }),
  });
  if (!response.ok) {
    throw await responseError(response, "Não foi possível consultar o Copiloto agora.");
  }
  return (await response.json()) as CopilotResponse;
}
