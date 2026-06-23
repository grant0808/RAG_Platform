"use client";

import { useEffect, useMemo, useState } from "react";

import { EmptyState, PageHeading, formatDate } from "@/components/ui";
import { api } from "@/lib/api";
import type { AppSnapshot, Pipeline, PipelineVersion, ProviderName, Strategy, ViewName } from "@/lib/types";

export function PipelineView({
  snapshot,
  pipeline,
  refresh,
  notify,
  onSelectPipeline,
  onNavigate,
}: {
  snapshot: AppSnapshot;
  pipeline: Pipeline | null;
  refresh: () => Promise<void>;
  notify: (message: string) => void;
  onSelectPipeline: (id: string) => void;
  onNavigate: (view: ViewName) => void;
}) {
  const [draft, setDraft] = useState<Pipeline | null>(pipeline);
  const [versions, setVersions] = useState<PipelineVersion[]>([]);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<"flow" | "versions">("flow");

  useEffect(() => setDraft(pipeline), [pipeline]);
  useEffect(() => {
    if (!pipeline) { setVersions([]); return; }
    void api.listVersions(pipeline.id).then(setVersions).catch(() => setVersions([]));
  }, [pipeline]);

  const models = useMemo(() => {
    if (!draft) return [];
    const discovered = snapshot.providers.find((item) => item.provider === draft.provider)?.models ?? [];
    return [...new Set([draft.model, ...discovered])];
  }, [draft, snapshot.providers]);

  if (!pipeline || !draft) {
    return <section className="page"><PageHeading index="04" title="Shape the" outline="reasoning." description="Provider를 연결한 뒤 첫 Pipeline을 생성하세요." /><EmptyState title="Pipeline이 없습니다.">상단의 New pipeline 버튼으로 실행 설정을 만드세요.</EmptyState></section>;
  }

  function update<K extends keyof Pipeline>(key: K, value: Pipeline[K]) {
    setDraft((current) => current ? { ...current, [key]: value } : current);
  }

  async function saveDraft() {
    if (!pipeline || !draft) return;
    setBusy(true);
    try {
      await api.updatePipeline(pipeline.id, {
        name: draft.name,
        strategy: draft.strategy,
        provider: draft.provider,
        model: draft.model,
        system_prompt: draft.system_prompt,
        top_k: draft.top_k,
        similarity_threshold: draft.similarity_threshold,
      });
      notify("Draft 설정을 저장했습니다.");
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Draft 저장에 실패했습니다.");
    } finally { setBusy(false); }
  }

  async function saveVersion() {
    if (!pipeline || !draft) return;
    setBusy(true);
    try {
      await api.updatePipeline(pipeline.id, {
        name: draft.name,
        strategy: draft.strategy,
        provider: draft.provider,
        model: draft.model,
        system_prompt: draft.system_prompt,
        top_k: draft.top_k,
        similarity_threshold: draft.similarity_threshold,
      });
      const version = await api.saveVersion(pipeline.id);
      notify(`불변 버전 v${version.version}을 저장했습니다.`);
      setVersions(await api.listVersions(pipeline.id));
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "버전 저장에 실패했습니다.");
    } finally { setBusy(false); }
  }

  async function rollback(version: number) {
    if (!pipeline) return;
    if (!window.confirm(`v${version} 설정을 새 head 버전으로 복원할까요?`)) return;
    setBusy(true);
    try {
      const restored = await api.rollback(pipeline.id, version);
      notify(`v${version} 설정을 v${restored.current_version}으로 복원했습니다.`);
      await refresh();
      setVersions(await api.listVersions(pipeline.id));
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "롤백에 실패했습니다.");
    } finally { setBusy(false); }
  }

  async function deletePipeline() {
    if (!pipeline) return;
    if (!window.confirm(`"${pipeline.name}" Pipeline을 삭제할까요? 저장된 버전과 배포 엔드포인트도 함께 삭제됩니다.`)) return;
    setBusy(true);
    try {
      await api.deletePipeline(pipeline.id);
      notify("Pipeline과 관련 버전/배포를 삭제했습니다.");
      await refresh();
      onNavigate("overview");
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Pipeline 삭제에 실패했습니다.");
    } finally { setBusy(false); }
  }

  return (
    <section className="page">
      <PageHeading index="04" title="Shape the" outline="reasoning." description="설정 변경은 Draft에, 실행 가능한 기준점은 불변 Pipeline Version에 저장합니다." action={<div className="heading-actions"><button className="button danger" disabled={busy} onClick={() => void deletePipeline()}>Delete</button><button className="button" disabled={busy} onClick={() => void saveDraft()}>Save draft</button><button className="button primary" disabled={busy} onClick={() => void saveVersion()}>Save v{pipeline.current_version + 1}</button></div>} />
      <div className="pipeline-switcher"><span>ACTIVE PIPELINE</span><select value={pipeline.id} onChange={(event) => onSelectPipeline(event.target.value)}>{snapshot.pipelines.map((item) => <option key={item.id} value={item.id}>{item.name} / v{item.current_version}</option>)}</select><div className="segmented"><button className={tab === "flow" ? "active" : ""} onClick={() => setTab("flow")}>Flow</button><button className={tab === "versions" ? "active" : ""} onClick={() => setTab("versions")}>Versions</button></div></div>
      {tab === "flow" ? (
        <div className="studio-shell">
          <div className="flow-canvas">
            <div className="flow-line" />
            <FlowNode index="01" icon="▥" title={draft.strategy === "tag" ? "Table catalog" : "Knowledge index"} detail={draft.strategy === "tag" ? "DuckDB schema" : `${snapshot.sources.length} sources`} />
            <FlowNode index="02" icon={draft.strategy[0].toUpperCase()} title={`${draft.strategy.toUpperCase()} Runnable`} detail={draft.strategy === "rag" ? "Vector Retriever" : draft.strategy === "tag" ? "Safe SQL Tool" : "Cache → RAG"} accent />
            <FlowNode index="03" icon="✣" title="Chat model" detail={`${draft.provider} / ${draft.model}`} />
            <FlowNode index="04" icon="↗" title="Response" detail="SSE · citations · trace" />
            <div className="flow-legend"><span>LANGCHAIN EXECUTION GRAPH</span><strong>Runnable → Adapter → DTO</strong></div>
          </div>
          <aside className="inspector">
            <div className="inspector-head"><span>PIPELINE / DRAFT</span><h2>Execution config</h2></div>
            <label className="field"><span>Name</span><input value={draft.name} onChange={(event) => update("name", event.target.value)} /></label>
            <label className="field"><span>Strategy</span><select value={draft.strategy} onChange={(event) => update("strategy", event.target.value as Strategy)}><option value="rag">RAG / document retrieval</option><option value="tag">TAG / table query</option><option value="cag">CAG / cache fallback</option></select></label>
            <div className="field-pair"><label className="field"><span>Provider</span><select value={draft.provider} onChange={(event) => { const provider = event.target.value as ProviderName; update("provider", provider); const first = snapshot.providers.find((item) => item.provider === provider)?.models[0]; if (first) update("model", first); }}>{snapshot.providers.map((provider) => <option key={provider.provider}>{provider.provider}</option>)}</select></label><label className="field"><span>Model</span><select value={draft.model} onChange={(event) => update("model", event.target.value)}>{models.map((model) => <option key={model}>{model}</option>)}</select></label></div>
            <label className="field"><span>System prompt</span><textarea value={draft.system_prompt} rows={6} onChange={(event) => update("system_prompt", event.target.value)} /></label>
            <label className="range-field"><span><b>Retrieval top K</b><output>{draft.top_k}</output></span><input type="range" min="1" max="20" value={draft.top_k} onChange={(event) => update("top_k", Number(event.target.value))} /></label>
            <label className="range-field"><span><b>Similarity threshold</b><output>{draft.similarity_threshold.toFixed(2)}</output></span><input type="range" min="0" max="1" step="0.05" value={draft.similarity_threshold} onChange={(event) => update("similarity_threshold", Number(event.target.value))} /></label>
            <button className="button acid full" onClick={() => onNavigate("playground")}>Test this pipeline →</button>
          </aside>
        </div>
      ) : (
        <div className="version-list">
          {versions.map((version, index) => <article key={version.id} className={index === 0 ? "current" : ""}><div><span>VERSION / {String(version.version).padStart(2, "0")}</span><strong>{version.config.name}</strong><small>{formatDate(version.created_at)}</small></div><div className="version-config"><span>{version.config.strategy.toUpperCase()}</span><span>{version.config.provider}</span><span>{version.config.model}</span><span>topK {version.config.top_k}</span></div><button className="button" disabled={index === 0 || busy} onClick={() => void rollback(version.version)}>{index === 0 ? "Current head" : "Rollback"}</button></article>)}
        </div>
      )}
    </section>
  );
}

function FlowNode({ index, icon, title, detail, accent = false }: { index: string; icon: string; title: string; detail: string; accent?: boolean }) {
  return <article className={`flow-node ${accent ? "accent" : ""}`}><span>NODE / {index}</span><b>{icon}</b><h3>{title}</h3><p>{detail}</p></article>;
}
