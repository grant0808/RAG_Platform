"use client";

import { type KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";

import { EmptyState, PageHeading } from "@/components/ui";
import { useChatAutoScroll } from "@/hooks/use-chat-auto-scroll";
import { api, streamChat } from "@/lib/api";
import type {
  AppSnapshot,
  ChatResponse,
  ChatSession,
  Citation,
  EvaluationResult,
  Pipeline,
  RagasDatasetItem,
  RagasEvaluationResult,
  RagasEvaluationSummary,
  SourceReference,
  Strategy,
  TraceEvent,
} from "@/lib/types";

type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  result?: ChatResponse;
  citations?: Citation[];
  sources?: SourceReference[];
};

const EMPTY_MESSAGE: Message = {
  id: "empty",
  role: "assistant",
  text: "질문을 입력하거나 이전 session을 선택하세요. token, citation, trace event가 실시간으로 표시됩니다.",
};

export function PlaygroundView({
  snapshot,
  pipeline,
  onSelectPipeline,
  notify,
}: {
  snapshot: AppSnapshot;
  pipeline: Pipeline | null;
  refresh: () => Promise<void>;
  onSelectPipeline: (id: string) => void;
  notify: (message: string) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([EMPTY_MESSAGE]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionTitleDraft, setSessionTitleDraft] = useState("");
  const [traces, setTraces] = useState<TraceEvent[]>([]);
  const [strategy, setStrategy] = useState<Strategy>(pipeline?.strategy ?? "rag");
  const [running, setRunning] = useState(false);
  const [ragasRunning, setRagasRunning] = useState(false);
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [ragasResult, setRagasResult] = useState<RagasEvaluationResult | null>(null);
  const [ragasRuns, setRagasRuns] = useState<RagasEvaluationSummary[]>([]);
  const [loadingSessionMessages, setLoadingSessionMessages] = useState(false);
  const loadedSessionScrollTargetRef = useRef<string | null>(null);
  const messageSignature = messages
    .map((message) => `${message.id}:${message.text.length}:${message.citations?.length ?? 0}`)
    .join("|");
  const hasLoadedNonEmptyMessages = !(
    messages.length === 0 ||
    (messages.length === 1 && messages[0].id === EMPTY_MESSAGE.id)
  );
  const {
    scrollContainerRef,
    bottomRef,
    handleScroll,
    scheduleScrollToBottom,
  } = useChatAutoScroll({ threshold: 120 });

  const loadSessions = useCallback(
    async (pipelineId: string) => {
      try {
        setSessions(await api.listChatSessions(pipelineId));
      } catch (caught) {
        notify(caught instanceof Error ? caught.message : "Chat sessions를 불러오지 못했습니다.");
      }
    },
    [notify],
  );

  const loadRagasRuns = useCallback(async () => {
    try {
      const runs = await api.listRagasEvaluations();
      setRagasRuns(runs);
    } catch {
      setRagasRuns([]);
    }
  }, []);

  useEffect(() => {
    if (!pipeline) return;
    setStrategy(pipeline.strategy);
    setActiveSessionId(null);
    setSessionTitleDraft("");
    setMessages([EMPTY_MESSAGE]);
    setTraces([]);
    void loadSessions(pipeline.id);
    void loadRagasRuns();
  }, [loadRagasRuns, loadSessions, pipeline]);

  useEffect(() => {
    if (loadingSessionMessages) return;
    if (!activeSessionId || loadedSessionScrollTargetRef.current !== activeSessionId) return;
    if (!hasLoadedNonEmptyMessages) return;
    scheduleScrollToBottom("auto", { force: true, doubleFrame: true });
    loadedSessionScrollTargetRef.current = null;
  }, [
    activeSessionId,
    hasLoadedNonEmptyMessages,
    loadingSessionMessages,
    scheduleScrollToBottom,
  ]);

  useEffect(() => {
    if (loadingSessionMessages) return;
    if (loadedSessionScrollTargetRef.current) return;
    scheduleScrollToBottom(running ? "auto" : "smooth", { doubleFrame: true });
  }, [loadingSessionMessages, messageSignature, running, scheduleScrollToBottom]);

  if (!pipeline) {
    return (
      <section className="page">
        <PageHeading
          index="05"
          title="Test with"
          outline="evidence."
          description="Chat runtime을 실행하기 전에 pipeline을 선택하거나 생성하세요."
        />
        <EmptyState title="선택된 pipeline이 없습니다.">먼저 Pipeline Studio에서 pipeline을 생성하세요.</EmptyState>
      </section>
    );
  }

  async function loadMessages(sessionId: string) {
    setActiveSessionId(sessionId);
    setSessionTitleDraft(sessions.find((session) => session.id === sessionId)?.title ?? "");
    setTraces([]);
    setLoadingSessionMessages(true);
    loadedSessionScrollTargetRef.current = sessionId;
    try {
      const history = await api.listChatMessages(sessionId);
      setMessages(
        history.length
          ? history.map((message) => ({
              id: message.id,
              role: message.role,
              text: message.content,
              sources: message.sources ?? readSources(message.message_metadata),
              result: readResult(message),
            }))
          : [EMPTY_MESSAGE],
      );
    } catch (caught) {
      loadedSessionScrollTargetRef.current = null;
      notify(caught instanceof Error ? caught.message : "Session messages를 불러오지 못했습니다.");
    } finally {
      setLoadingSessionMessages(false);
    }
  }

  async function newSession() {
    if (!pipeline) return;
    try {
      const session = await api.createChatSession(pipeline.id);
      setSessions((current) => [session, ...current]);
      setActiveSessionId(session.id);
      setSessionTitleDraft(session.title);
      setMessages([EMPTY_MESSAGE]);
      setTraces([]);
      scheduleScrollToBottom("auto", { force: true });
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Session을 생성하지 못했습니다.");
    }
  }

  async function deleteSession() {
    if (!pipeline || !activeSessionId || !window.confirm("현재 chat session을 삭제할까요?")) return;
    const currentPipeline = pipeline;
    try {
      await api.deleteChatSession(activeSessionId);
      setActiveSessionId(null);
      setSessionTitleDraft("");
      setMessages([EMPTY_MESSAGE]);
      scheduleScrollToBottom("auto", { force: true });
      await loadSessions(currentPipeline.id);
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Session을 삭제하지 못했습니다.");
    }
  }

  async function renameSession() {
    if (!activeSessionId || !pipeline) return;
    const title = sessionTitleDraft.trim();
    if (!title) {
      notify("Session name을 입력하세요.");
      return;
    }
    try {
      const updated = await api.updateChatSession(activeSessionId, title);
      setSessions((current) =>
        current.map((session) => (session.id === updated.id ? updated : session)),
      );
      setSessionTitleDraft(updated.title);
      notify("Session name을 저장했습니다.");
      await loadSessions(pipeline.id);
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Session name을 저장하지 못했습니다.");
    }
  }

  async function submit(form: FormData) {
    if (!pipeline) return;
    const text = String(form.get("message")).trim();
    if (!text || running) return;
    const userId = `user-${Date.now()}`;
    const assistantId = `assistant-${Date.now()}`;
    setMessages((current) => [
      ...(current.length === 1 && current[0].id === "empty" ? [] : current),
      { id: userId, role: "user", text },
      { id: assistantId, role: "assistant", text: "", citations: [] },
    ]);
    scheduleScrollToBottom("smooth", { force: true, doubleFrame: true });
    setTraces([]);
    setRunning(true);
    try {
      await streamChat(pipeline.id, activeSessionId, text, strategy, {
        onToken: (token) =>
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId ? { ...message, text: message.text + token } : message,
            ),
          ),
        onTrace: (trace) => setTraces((current) => [...current, trace]),
        onCitation: (citation) =>
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId
                ? { ...message, citations: [...(message.citations ?? []), citation] }
                : message,
            ),
          ),
        onDone: (result) => {
          setActiveSessionId(result.conversation_id ?? result.session_id);
          const knownSession = sessions.find((session) => session.id === (result.conversation_id ?? result.session_id));
          if (knownSession) setSessionTitleDraft(knownSession.title);
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId
                ? { ...message, id: result.message_id ?? message.id, text: result.answer, result, citations: result.citations, sources: result.sources }
                : message,
            ),
          );
          scheduleScrollToBottom("auto", { doubleFrame: true });
          setTraces(result.trace);
          void loadSessions(pipeline.id);
        },
      });
    } catch (caught) {
      const error = caught instanceof Error ? caught.message : "Runtime execution failed.";
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId ? { ...message, text: `실행 오류: ${error}` } : message,
        ),
      );
      scheduleScrollToBottom("smooth", { force: true, doubleFrame: true });
    } finally {
      setRunning(false);
    }
  }

  async function evaluate() {
    if (!pipeline) return;
    setRunning(true);
    try {
      const result = await api.evaluate(pipeline.id, []);
      setEvaluation(result);
      notify("기본 evaluation questions 3개를 실행했습니다.");
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Evaluation 실행에 실패했습니다.");
    } finally {
      setRunning(false);
    }
  }

  async function runRagas() {
    if (!pipeline) return;
    setRagasRunning(true);
    try {
      const result = await api.runRagasEvaluation(
        pipeline.id,
        buildRagasDataset(lastResult),
        `playground-${new Date().toISOString()}`,
      );
      setRagasResult(result);
      await loadRagasRuns();
      notify("RAGAS evaluation을 실행했습니다.");
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "RAGAS evaluation 실행에 실패했습니다.");
    } finally {
      setRagasRunning(false);
    }
  }

  function handleMessageKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    if (!running) event.currentTarget.form?.requestSubmit();
  }

  const lastResult = [...messages].reverse().find((message) => message.result)?.result;
  return (
    <section className="page playground-page">
      <PageHeading
        index="05"
        title="Test with"
        outline="evidence."
        description="SSE token, citation, LangChain trace event를 하나의 runtime frame에서 확인합니다."
        action={
          <div className="top-actions">
            <button className="button" disabled={running} onClick={() => void evaluate()}>
              Run evaluation
            </button>
            <button className="button acid" disabled={ragasRunning} onClick={() => void runRagas()}>
              Run RAGAS
            </button>
          </div>
        }
      />
      <div className="playground-toolbar">
        <label>
          <span>PIPELINE</span>
          <select
            value={pipeline.id}
            onChange={(event) => {
              const selected = snapshot.pipelines.find((item) => item.id === event.target.value);
              onSelectPipeline(event.target.value);
              if (selected) setStrategy(selected.strategy);
            }}
          >
            {snapshot.pipelines.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} / v{item.current_version}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>SESSION</span>
          <select
            value={activeSessionId ?? ""}
            onChange={(event) => {
              if (event.target.value) void loadMessages(event.target.value);
              else {
                setActiveSessionId(null);
                setSessionTitleDraft("");
                setMessages([EMPTY_MESSAGE]);
              }
            }}
          >
            <option value="">Auto session</option>
            {sessions.map((session) => (
              <option key={session.id} value={session.id}>
                {session.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>STRATEGY OVERRIDE</span>
          <select value={strategy} onChange={(event) => setStrategy(event.target.value as Strategy)}>
            <option value="rag">RAG</option>
          </select>
        </label>
        <div>
          <span>MODEL</span>
          <strong>{pipeline.provider} / {pipeline.model}</strong>
        </div>
      </div>
      <div className="playground-layout">
        <div className="chat-panel">
          <div className="session-actions">
            <button className="button" disabled={running} onClick={() => void newSession()}>
              New chat
            </button>
            <input
              value={sessionTitleDraft}
              disabled={!activeSessionId || running}
              placeholder="Session name"
              maxLength={160}
              onChange={(event) => setSessionTitleDraft(event.target.value)}
            />
            <button className="button" disabled={running || !activeSessionId} onClick={() => void renameSession()}>
              Save name
            </button>
            <button className="button danger" disabled={running || !activeSessionId} onClick={() => void deleteSession()}>
              Delete chat
            </button>
            <span>{activeSessionId ? `Session ${activeSessionId.slice(0, 8)}` : "첫 메시지 전송 시 session 자동 생성"}</span>
          </div>
          <div
            ref={scrollContainerRef}
            className="messages"
            aria-live="polite"
            onScroll={handleScroll}
          >
            {messages.map((message) => (
              <article key={message.id} className={`message ${message.role}`}>
                <span>{message.role === "user" ? "YOU" : `FOUNDRY / ${(message.result?.route ?? message.result?.strategy ?? "ready").toUpperCase()}`}</span>
                <div>{message.text || <span className="typing">Running...</span>}</div>
                {message.result && (
                  <div className="message-meta">
                    <span>{message.result.route}</span>
                    <span>{message.result.selected_tool ?? "none"}</span>
                    <span>{message.result.memory_used ? `memory ${message.result.history_count}` : "memory off"}</span>
                  </div>
                )}
                {message.sources && message.sources.length > 0 && (
                  <SourceList sources={message.sources} />
                )}
                {message.citations && message.citations.length > 0 && (
                  <footer>
                    {message.citations.map((citation, index) => (
                      <span key={`${citation.source_id}-${index}`}>
                        {citation.source_name} / {citation.location ?? "source"}
                      </span>
                    ))}
                  </footer>
                )}
              </article>
            ))}
            <div ref={bottomRef} aria-hidden="true" />
          </div>
          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault();
              const form = event.currentTarget;
              void submit(new FormData(form)).then(() => form.reset());
            }}
          >
            <textarea
              name="message"
              placeholder="질문을 입력하세요. /status로 token 사용량을 확인할 수 있습니다."
              required
              maxLength={20000}
              onKeyDown={handleMessageKeyDown}
            />
            <button disabled={running} aria-label="질문 전송">
              {running ? "..." : "GO"}
            </button>
          </form>
        </div>
        <aside className="trace-panel">
          <header>
            <span>LIVE / LANGCHAIN TRACE</span>
            <h2>Runnable execution</h2>
          </header>
          <div className="trace-list">
            {traces.length === 0 ? (
              <p>질문을 실행하면 retriever와 model 단계가 표시됩니다.</p>
            ) : (
              traces.map((trace, index) => (
                <div key={`${trace.step}-${index}`}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <strong>{trace.step}</strong>
                    <small>{JSON.stringify(trace.metadata)}</small>
                  </div>
                  <b>{trace.duration_ms ? `${trace.duration_ms}ms` : trace.status}</b>
                </div>
              ))
            )}
          </div>
          <div className="trace-metrics">
            <div>
              <span>ROUTE</span>
              <b>{lastResult?.route?.toUpperCase() ?? strategy.toUpperCase()}</b>
            </div>
            <div>
              <span>MODEL</span>
              <b>{lastResult?.model ?? pipeline.model}</b>
            </div>
            <div>
              <span>TOKENS</span>
              <b>{lastResult?.usage.total_tokens ?? "--"}</b>
            </div>
            <div>
              <span>MEMORY</span>
              <b>{lastResult?.memory_used ? lastResult.history_count : 0}</b>
            </div>
          </div>
          {evaluation && (
            <div className="evaluation-card">
              <span>POC EVALUATION</span>
              <strong>{Math.round(evaluation.average_accuracy_score * 100)}%</strong>
              <dl>
                <div>
                  <dt>Latency</dt>
                  <dd>{evaluation.average_latency_seconds}s</dd>
                </div>
                <div>
                  <dt>Est. cost</dt>
                  <dd>${evaluation.total_estimated_cost}</dd>
                </div>
              </dl>
            </div>
          )}
          {ragasResult && (
            <div className="evaluation-card ragas-card">
              <span>RAGAS / {ragasResult.ragas_backend}</span>
              <strong>{formatScore(ragasResult.averages.faithfulness)}</strong>
              <dl>
                <div>
                  <dt>Answer relevancy</dt>
                  <dd>{formatScore(ragasResult.averages.answer_relevancy)}</dd>
                </div>
                <div>
                  <dt>Context precision</dt>
                  <dd>{formatScore(ragasResult.averages.context_precision)}</dd>
                </div>
                <div>
                  <dt>Context recall</dt>
                  <dd>{formatScore(ragasResult.averages.context_recall)}</dd>
                </div>
              </dl>
            </div>
          )}
          <div className="ragas-runs">
            <span>RECENT RAGAS RUNS</span>
            {ragasRuns.filter((run) => run.pipeline_id === pipeline.id).slice(0, 4).length === 0 ? (
              <p>No RAGAS runs yet.</p>
            ) : (
              ragasRuns
                .filter((run) => run.pipeline_id === pipeline.id)
                .slice(0, 4)
                .map((run) => (
                  <div key={run.id}>
                    <strong>{run.run_name ?? run.id.slice(0, 8)}</strong>
                    <small>{formatScore(run.averages?.faithfulness)} faithfulness</small>
                  </div>
                ))
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}

function readSources(metadata: Record<string, unknown>): SourceReference[] {
  return Array.isArray(metadata.sources) ? (metadata.sources as SourceReference[]) : [];
}

function buildRagasDataset(lastResult: ChatResponse | undefined): RagasDatasetItem[] {
  if (!lastResult?.query || !lastResult.answer) {
    return [
      {
        question: "RAG pipeline smoke evaluation",
        ground_truth: "The answer should be grounded in retrieved context and return sources.",
        contexts: [],
        metadata: { source: "playground-default" },
      },
    ];
  }
  return [
    {
      question: lastResult.query,
      answer: lastResult.answer,
      contexts: extractContextText(lastResult.contexts),
      ground_truth: lastResult.answer,
      metadata: {
        route: lastResult.route,
        selected_tool: lastResult.selected_tool,
        source: "playground-last-response",
      },
    },
  ];
}

function extractContextText(contexts: unknown[]): string[] {
  return contexts
    .map((context) => {
      if (typeof context === "string") return context;
      if (isRecord(context) && typeof context.content === "string") return context.content;
      return "";
    })
    .filter(Boolean);
}

function formatScore(value: unknown): string {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "--";
}

function readResult(message: { message_metadata: Record<string, unknown> }): ChatResponse | undefined {
  const metadata = message.message_metadata;
  const route = metadata.route;
  if (typeof route !== "string") return undefined;
  return {
    session_id: null,
    conversation_id: null,
    message_id: null,
    answer: "",
    strategy: typeof metadata.strategy === "string" ? metadata.strategy : "rag",
    provider: "",
    model: "",
    route: route === "general" || route === "web_fallback" ? route : "rag",
    selected_tool: typeof metadata.selected_tool === "string" ? metadata.selected_tool : null,
    citations: Array.isArray(metadata.citations) ? (metadata.citations as Citation[]) : [],
    trace: Array.isArray(metadata.trace) ? (metadata.trace as TraceEvent[]) : [],
    usage: isRecord(metadata.usage) ? (metadata.usage as Record<string, number>) : {},
    sources: readSources(metadata),
    contexts: Array.isArray(metadata.contexts) ? metadata.contexts : [],
    web_results: Array.isArray(metadata.web_results) ? (metadata.web_results as ChatResponse["web_results"]) : [],
    cached: Boolean(metadata.cached),
    memory_used: Boolean(metadata.memory_used),
    history_count: typeof metadata.history_count === "number" ? metadata.history_count : 0,
  };
}

function SourceList({ sources }: { sources: SourceReference[] }) {
  return (
    <div className="source-list">
      {sources.map((source, index) => {
        if (isWebSource(source)) {
          return (
            <a key={`${source.url}-${index}`} href={source.url} target="_blank" rel="noreferrer">
              <strong>{source.title || "Web source"}</strong>
              <span>{source.provider ?? "web"} / {source.snippet}</span>
            </a>
          );
        }
        const record = source as Record<string, unknown>;
        const filename = record.filename ?? record.source_name ?? record.source ?? "PDF source";
        const page = record.page ?? record.location ?? "-";
        const chunk = record.chunk_id ?? "-";
        const score = record.rerank_score ?? record.score ?? "-";
        return (
          <div key={`${String(filename)}-${index}`}>
            <strong>{String(filename)}</strong>
            <span>page {String(page)} / chunk {String(chunk)} / score {String(score)}</span>
          </div>
        );
      })}
    </div>
  );
}

function isWebSource(source: SourceReference): source is ChatResponse["web_results"][number] {
  return isRecord(source) && typeof source.url === "string" && typeof source.snippet === "string";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
