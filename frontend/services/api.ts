export type DashboardStats = {
  base_ready: number;
  evidence_count: number;
  risk_count: number;
  pending_confirmation_count: number;
};

export type CopilotMessagePayload = {
  role: "user" | "assistant";
  content: string;
};

type CopilotResponse = {
  answer: string;
  model: string;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL;
const REQUEST_TIMEOUT_MS = 12_000;

function apiEndpoint(path: string): string {
  if (!apiUrl) {
    throw new Error("NEXT_PUBLIC_API_URL nao foi configurada.");
  }

  return `${apiUrl.replace(/\/$/, "")}${path}`;
}

async function fetchApi(path: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    return await fetch(apiEndpoint(path), { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("A API demorou mais do que o esperado. Tente novamente em instantes.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await fetchApi("/api/dashboard/stats", {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error("Nao foi possivel carregar os indicadores do painel.");
  }

  return (await response.json()) as DashboardStats;
}

export async function askCopilot(input: {
  messages: CopilotMessagePayload[];
  currentArea: string;
  context: string;
}): Promise<CopilotResponse> {
  const response = await fetchApi("/api/copilot", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: input.messages.slice(-12),
      current_area: input.currentArea,
      context: input.context,
    }),
  });

  if (!response.ok) {
    throw new Error("Nao foi possivel consultar o Copiloto agora.");
  }

  return (await response.json()) as CopilotResponse;
}
