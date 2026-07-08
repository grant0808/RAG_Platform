export type ViewName =
  | "overview"
  | "sources"
  | "providers"
  | "pipeline"
  | "playground"
  | "deployments";

export type Strategy = "rag";
export type ProviderName = "openai" | "anthropic" | "ollama";
export type DeploymentEnvironment = "preview" | "production";
export type DeploymentStatus = "running" | "stopped";

export interface Health {
  status: string;
  service: string;
  version: string;
  auth_enabled: boolean;
}

export interface Provider {
  provider: ProviderName;
  masked_key: string;
  status: string;
  models: string[];
  last_validated_at: string;
}

export interface Source {
  id: string;
  name: string;
  kind: string;
  status: string;
  table_name: string | null;
  chunk_count: number;
  size_bytes: number;
  created_at: string;
}

export interface Pipeline {
  id: string;
  name: string;
  strategy: Strategy;
  provider: ProviderName;
  model: string;
  system_prompt: string;
  top_k: number;
  similarity_threshold: number;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface PipelineVersion {
  id: string;
  pipeline_id: string;
  version: number;
  config: Omit<Pipeline, "id" | "current_version" | "created_at" | "updated_at">;
  created_at: string;
}

export interface Deployment {
  id: string;
  pipeline_id: string;
  slug: string;
  version: number;
  environment: DeploymentEnvironment;
  status: DeploymentStatus;
  created_at: string;
}

export interface Citation {
  source_id: string;
  source_name: string;
  location: string | null;
  score: number | null;
  url?: string | null;
  provider?: string | null;
}

export interface TraceEvent {
  step: string;
  status: "started" | "completed" | "failed";
  duration_ms: number | null;
  metadata: Record<string, unknown>;
}

export interface ChatResponse {
  session_id: string | null;
  conversation_id: string | null;
  message_id: string | null;
  query?: string | null;
  rewritten_query?: string | null;
  route: "general" | "rag" | "web_fallback";
  selected_tool?: string | null;
  answer: string;
  strategy: string;
  provider: string;
  model: string;
  citations: Citation[];
  trace: TraceEvent[];
  usage: Record<string, number>;
  sources: SourceReference[];
  contexts: unknown[];
  web_results: WebSourceReference[];
  cached: boolean;
  memory_used: boolean;
  history_count: number;
  token_status?: {
    budget: number;
    used_total: number;
    used_input: number;
    used_output: number;
    remaining: number;
    message_count: number;
  };
  provider_quota?: Record<string, unknown>;
}

export interface ChatSession {
  id: string;
  pipeline_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  message_id?: string | null;
  session_id: string;
  conversation_id?: string | null;
  role: "user" | "assistant";
  content: string;
  message_metadata: Record<string, unknown>;
  route?: "general" | "rag" | "web_fallback" | null;
  selected_tool?: string | null;
  sources?: SourceReference[];
  created_at: string;
}

export interface PdfSourceReference {
  type: "pdf" | "document";
  source?: string | null;
  source_id?: string | null;
  source_name?: string | null;
  filename?: string | null;
  page?: number | string | null;
  chunk_id?: string | null;
  score?: number | null;
  rerank_score?: number | null;
  location?: string | null;
}

export interface WebSourceReference {
  type?: "web";
  title: string;
  url: string;
  snippet: string;
  provider?: string;
}

export type SourceReference = PdfSourceReference | WebSourceReference | Record<string, unknown>;

export interface EvaluationResult {
  pipeline_id: string;
  executed_at: string;
  average_latency_seconds: number;
  total_estimated_cost: number;
  average_accuracy_score: number;
  metrics: Array<{
    query: string;
    strategy: string;
    latency_seconds: number;
    estimated_cost: number;
    accuracy_score: number;
  }>;
}

export interface RagasDatasetItem {
  question: string;
  answer?: string | null;
  contexts?: string[];
  ground_truth: string;
  metadata?: Record<string, unknown>;
}

export interface RagasMetricScore {
  question: string;
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
  route: string;
  latency_ms: number | null;
}

export interface RagasEvaluationResult {
  id: string;
  pipeline_id: string;
  run_name: string;
  executed_at: string;
  result_path: string;
  metrics: RagasMetricScore[];
  averages: Record<string, number>;
  config: Record<string, unknown>;
  ragas_backend: string;
}

export interface RagasEvaluationSummary {
  id: string;
  run_name: string | null;
  pipeline_id: string | null;
  executed_at: string | null;
  averages: Record<string, number>;
  result_path: string;
}

export interface AppSnapshot {
  health: Health | null;
  providers: Provider[];
  sources: Source[];
  pipelines: Pipeline[];
  deployments: Deployment[];
}
