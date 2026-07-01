"use client";

import { type KeyboardEvent, useCallback, useEffect, useState } from "react";

import { EmptyState, PageHeading } from "@/components/ui";
import { api, streamChat } from "@/lib/api";
import type {
  AppSnapshot,
  ChatResponse,
  ChatSession,
  Citation,
  EvaluationResult,
  Pipeline,
  Strategy,
  TraceEvent,
} from "@/lib/types";

type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  result?: ChatResponse;
  citations?: Citation[];
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
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);

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

  useEffect(() => {
    if (!pipeline) return;
    setStrategy(pipeline.strategy);
    setActiveSessionId(null);
    setSessionTitleDraft("");
    setMessages([EMPTY_MESSAGE]);
    setTraces([]);
    void loadSessions(pipeline.id);
  }, [loadSessions, pipeline]);

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
    try {
      const history = await api.listChatMessages(sessionId);
      setMessages(
        history.length
          ? history.map((message) => ({
              id: message.id,
              role: message.role,
              text: message.content,
            }))
          : [EMPTY_MESSAGE],
      );
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Session messages를 불러오지 못했습니다.");
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
          setActiveSessionId(result.session_id);
          const knownSession = sessions.find((session) => session.id === result.session_id);
          if (knownSession) setSessionTitleDraft(knownSession.title);
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId
                ? { ...message, text: result.answer, result, citations: result.citations }
                : message,
            ),
          );
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
          <button className="button" disabled={running} onClick={() => void evaluate()}>
            Run evaluation
          </button>
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
          <div className="messages" aria-live="polite">
            {messages.map((message) => (
              <article key={message.id} className={`message ${message.role}`}>
                <span>{message.role === "user" ? "YOU" : `FOUNDRY / ${message.result?.strategy?.toUpperCase() ?? "READY"}`}</span>
                <div>{message.text || <span className="typing">Running...</span>}</div>
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
              <span>STRATEGY</span>
              <b>{lastResult?.strategy.toUpperCase() ?? strategy.toUpperCase()}</b>
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
              <span>CITATIONS</span>
              <b>{lastResult?.citations.length ?? 0}</b>
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
        </aside>
      </div>
    </section>
  );
}
