"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Sidebar } from "@/components/sidebar";
import { Spinner } from "@/components/ui";
import { DeploymentsView } from "@/components/views/deployments-view";
import { OverviewView } from "@/components/views/overview-view";
import { PipelineView } from "@/components/views/pipeline-view";
import { PlaygroundView } from "@/components/views/playground-view";
import { ProvidersView } from "@/components/views/providers-view";
import { SourcesView } from "@/components/views/sources-view";
import { api, loadSnapshot } from "@/lib/api";
import type { AppSnapshot, ProviderName, Strategy, ViewName } from "@/lib/types";

const emptySnapshot: AppSnapshot = {
  health: null,
  providers: [],
  sources: [],
  pipelines: [],
  deployments: [],
};
const DEFAULT_OPENAI_MODEL = "gpt-4o-mini";

export function Workbench() {
  const [view, setView] = useState<ViewName>("overview");
  const [snapshot, setSnapshot] = useState<AppSnapshot>(emptySnapshot);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [selectedPipelineId, setSelectedPipelineId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await loadSnapshot();
      setSnapshot(next);
      setError(null);
      setSelectedPipelineId((current) =>
        current && next.pipelines.some((pipeline) => pipeline.id === current)
          ? current
          : next.pipelines[0]?.id ?? null,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Backend API에 연결할 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const selectedPipeline = useMemo(
    () => snapshot.pipelines.find((pipeline) => pipeline.id === selectedPipelineId) ?? null,
    [selectedPipelineId, snapshot.pipelines],
  );

  function navigate(next: ViewName) {
    setView(next);
    setMenuOpen(false);
  }

  async function createPipeline(form: FormData) {
    setBusy(true);
    try {
      const provider = form.get("provider") as ProviderName;
      const connection = snapshot.providers.find((item) => item.provider === provider);
      const model = String(form.get("model") || connection?.models[0] || DEFAULT_OPENAI_MODEL);
      const created = await api.createPipeline({
        name: String(form.get("name")),
        strategy: form.get("strategy") as Strategy,
        provider,
        model,
      });
      await refresh();
      setSelectedPipelineId(created.id);
      setDialogOpen(false);
      setView("pipeline");
      setToast(`Pipeline을 생성했습니다: ${created.name}`);
    } catch (caught) {
      setToast(caught instanceof Error ? caught.message : "Pipeline 생성에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  const viewProps = { snapshot, refresh, notify: setToast };
  let content;
  if (loading) {
    content = (
      <div className="full-state">
        <Spinner label="Loading workbench" />
      </div>
    );
  } else if (error) {
    content = (
      <div className="full-state error-state">
        <span>BACKEND / OFFLINE</span>
        <h1>API server required.</h1>
        <p>{error}</p>
        <code>cd backend && uv run uvicorn foundry.main:app --reload</code>
        <button className="button primary" onClick={() => void refresh()}>
          Retry connection
        </button>
      </div>
    );
  } else if (view === "overview") {
    content = (
      <OverviewView
        {...viewProps}
        onNavigate={navigate}
        onSelectPipeline={setSelectedPipelineId}
      />
    );
  } else if (view === "sources") {
    content = <SourcesView {...viewProps} />;
  } else if (view === "providers") {
    content = <ProvidersView {...viewProps} />;
  } else if (view === "pipeline") {
    content = (
      <PipelineView
        {...viewProps}
        pipeline={selectedPipeline}
        onSelectPipeline={setSelectedPipelineId}
        onNavigate={navigate}
      />
    );
  } else if (view === "playground") {
    content = (
      <PlaygroundView
        {...viewProps}
        pipeline={selectedPipeline}
        onSelectPipeline={setSelectedPipelineId}
      />
    );
  } else {
    content = <DeploymentsView {...viewProps} />;
  }

  const firstProvider = snapshot.providers[0];
  return (
    <div className="app-shell">
      <div className="grain" aria-hidden="true" />
      <Sidebar view={view} open={menuOpen} onNavigate={navigate} />
      <div className="workspace">
        <header className="topbar">
          <button
            className="menu-button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-label="Open navigation"
            aria-expanded={menuOpen}
          >
            =
          </button>
          <div className="workspace-switcher">
            <span className="signal-dot" />
            <span>Personal lab</span>
            <span className="slash">/</span>
            <strong>{selectedPipeline?.name ?? "No pipeline selected"}</strong>
          </div>
          <div className="top-actions">
            <span className="api-state">API {snapshot.health?.status.toUpperCase()}</span>
            <span className="provider-state">{firstProvider?.provider ?? "NO PROVIDER"}</span>
            <button className="button primary" onClick={() => setDialogOpen(true)}>
              + New pipeline
            </button>
          </div>
        </header>
        <main className="main-content">{content}</main>
      </div>

      {dialogOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setDialogOpen(false)}>
          <form
            className="modal"
            onSubmit={(event) => {
              event.preventDefault();
              void createPipeline(new FormData(event.currentTarget));
            }}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <span className="eyebrow">NEW / PIPELINE</span>
            <button
              type="button"
              className="modal-close"
              onClick={() => setDialogOpen(false)}
              aria-label="Close"
            >
              x
            </button>
            <h2>
              실행 가능한
              <br />
              knowledge pipeline을 설계하세요.
            </h2>
            <label className="field">
              <span>Name</span>
              <input name="name" defaultValue="Local knowledge assistant" required maxLength={120} />
            </label>
            <div className="field-pair">
              <label className="field">
                <span>Strategy</span>
                <select name="strategy" defaultValue="rag">
                  <option value="rag">RAG</option>
                  <option value="tag">TAG</option>
                  <option value="cag">CAG</option>
                </select>
              </label>
              <label className="field">
                <span>Provider</span>
                <select name="provider" defaultValue={firstProvider?.provider ?? "openai"}>
                  {snapshot.providers.map((provider) => (
                    <option key={provider.provider} value={provider.provider}>
                      {provider.provider}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="field">
              <span>Model ID</span>
              <input name="model" defaultValue={firstProvider?.models[0] ?? DEFAULT_OPENAI_MODEL} required />
            </label>
            <div className="modal-actions">
              <button type="button" className="button" onClick={() => setDialogOpen(false)}>
                Cancel
              </button>
              <button className="button primary" disabled={busy || !snapshot.providers.length}>
                {busy ? "Creating..." : "Create pipeline"}
              </button>
            </div>
          </form>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}
