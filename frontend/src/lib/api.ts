import type {
  AppSnapshot,
  ChatMessage,
  ChatResponse,
  ChatSession,
  Deployment,
  DeploymentEnvironment,
  DeploymentStatus,
  EvaluationResult,
  Pipeline,
  PipelineVersion,
  Provider,
  ProviderName,
  Source,
  Strategy,
  TraceEvent,
  Citation,
} from "@/lib/types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init?.body instanceof FormData
      ? init.headers
      : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.error?.message ?? body?.detail ?? `API request failed (${response.status})`;
    throw new ApiError(typeof message === "string" ? message : JSON.stringify(message), response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function loadSnapshot(): Promise<AppSnapshot> {
  const [health, providers, sources, pipelines, deployments] = await Promise.all([
    request<AppSnapshot["health"]>("/health"),
    request<Provider[]>("/providers"),
    request<Source[]>("/sources"),
    request<Pipeline[]>("/pipelines"),
    request<Deployment[]>("/deployments"),
  ]);
  return { health, providers, sources, pipelines, deployments };
}

export const api = {
  connectProvider: (provider: ProviderName, apiKey: string, validateConnection: boolean) =>
    request<Provider>(`/providers/${provider}`, {
      method: "PUT",
      body: JSON.stringify({ api_key: apiKey, validate_connection: validateConnection }),
    }),
  refreshProvider: (provider: ProviderName) =>
    request<Provider>(`/providers/${provider}/refresh-models`, { method: "POST" }),
  deleteProvider: (provider: ProviderName) =>
    request<void>(`/providers/${provider}`, { method: "DELETE" }),
  uploadSource: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Source>("/sources/upload", { method: "POST", body });
  },
  deleteSource: (id: string) => request<void>(`/sources/${id}`, { method: "DELETE" }),
  createPipeline: (payload: {
    name: string;
    strategy: Strategy;
    provider: ProviderName;
    model: string;
  }) => request<Pipeline>("/pipelines", { method: "POST", body: JSON.stringify(payload) }),
  updatePipeline: (id: string, payload: Partial<Pipeline>) =>
    request<Pipeline>(`/pipelines/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deletePipeline: (id: string) => request<void>(`/pipelines/${id}`, { method: "DELETE" }),
  saveVersion: (id: string) =>
    request<PipelineVersion>(`/pipelines/${id}/versions`, { method: "POST" }),
  listVersions: (id: string) => request<PipelineVersion[]>(`/pipelines/${id}/versions`),
  rollback: (id: string, version: number) =>
    request<Pipeline>(`/pipelines/${id}/rollback/${version}`, { method: "POST" }),
  createDeployment: (
    pipelineId: string,
    slug: string | null,
    environment: DeploymentEnvironment,
  ) =>
    request<Deployment>("/deployments", {
      method: "POST",
      body: JSON.stringify({ pipeline_id: pipelineId, slug: slug || null, environment }),
    }),
  updateDeployment: (
    deploymentId: string,
    payload: { environment?: DeploymentEnvironment; status?: DeploymentStatus },
  ) =>
    request<Deployment>(`/deployments/${deploymentId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  runDeployment: (deploymentId: string) =>
    request<Deployment>(`/deployments/${deploymentId}/run`, { method: "POST" }),
  stopDeployment: (deploymentId: string) =>
    request<Deployment>(`/deployments/${deploymentId}/stop`, { method: "POST" }),
  deleteDeployment: (deploymentId: string) =>
    request<void>(`/deployments/${deploymentId}`, { method: "DELETE" }),
  evaluate: (pipelineId: string, testQueries: string[]) =>
    request<EvaluationResult>("/evaluations/run", {
      method: "POST",
      body: JSON.stringify({ pipeline_id: pipelineId, test_queries: testQueries }),
    }),
  createChatSession: (pipelineId: string, title?: string) =>
    request<ChatSession>("/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ pipeline_id: pipelineId, title: title || null }),
    }),
  listChatSessions: (pipelineId: string) =>
    request<ChatSession[]>(`/chat/sessions?pipeline_id=${encodeURIComponent(pipelineId)}`),
  listChatMessages: (sessionId: string) =>
    request<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),
  deleteChatSession: (sessionId: string) =>
    request<void>(`/chat/sessions/${sessionId}`, { method: "DELETE" }),
};

type StreamHandlers = {
  onToken: (text: string) => void;
  onTrace: (trace: TraceEvent) => void;
  onCitation: (citation: Citation) => void;
  onDone: (result: ChatResponse) => void;
};

export async function streamChat(
  pipelineId: string,
  sessionId: string | null,
  message: string,
  strategy: Strategy,
  handlers: StreamHandlers,
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pipeline_id: pipelineId, session_id: sessionId, message, strategy }),
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.error?.message ?? `Stream failed (${response.status})`, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const event = frame.match(/^event:\s*(.+)$/m)?.[1];
      const rawData = frame.match(/^data:\s*(.+)$/m)?.[1];
      if (!event || !rawData) continue;
      const data: unknown = JSON.parse(rawData);
      if (event === "token") handlers.onToken((data as { text: string }).text);
      if (event === "trace") handlers.onTrace(data as TraceEvent);
      if (event === "citation") handlers.onCitation(data as Citation);
      if (event === "done") handlers.onDone(data as ChatResponse);
    }
    if (done) break;
  }
}
