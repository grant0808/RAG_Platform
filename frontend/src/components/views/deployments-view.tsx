"use client";

import { useState } from "react";

import { EmptyState, PageHeading, StatusBadge, formatDate } from "@/components/ui";
import { API_BASE, api } from "@/lib/api";
import type { AppSnapshot } from "@/lib/types";

export function DeploymentsView({ snapshot, refresh, notify }: { snapshot: AppSnapshot; refresh: () => Promise<void>; notify: (message: string) => void }) {
  const [creating, setCreating] = useState(false);

  async function create(form: FormData) {
    setCreating(true);
    try {
      const deployment = await api.createDeployment(String(form.get("pipelineId")), String(form.get("slug") || ""), String(form.get("status")));
      notify(`${deployment.slug} 배포를 생성했습니다.`);
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "배포 생성에 실패했습니다.");
    } finally { setCreating(false); }
  }

  async function copy(value: string) {
    await navigator.clipboard.writeText(value);
    notify("Endpoint를 복사했습니다.");
  }

  return (
    <section className="page">
      <PageHeading index="06" title="Deploy once." outline="Observe always." description="배포는 생성 시점의 불변 Pipeline Version을 가리키므로 이후 Draft 변경과 분리됩니다." />
      <form className="deployment-form" onSubmit={(event) => { event.preventDefault(); void create(new FormData(event.currentTarget)); }}><label><span>PIPELINE</span><select name="pipelineId" required>{snapshot.pipelines.map((pipeline) => <option key={pipeline.id} value={pipeline.id}>{pipeline.name} / v{pipeline.current_version}</option>)}</select></label><label><span>SLUG / OPTIONAL</span><input name="slug" placeholder="support-bot" pattern="[a-zA-Z0-9-]+" minLength={3} maxLength={80} /></label><label><span>ENVIRONMENT</span><select name="status"><option value="preview">Preview</option><option value="production">Production</option></select></label><button className="button acid" disabled={creating || !snapshot.pipelines.length}>{creating ? "Deploying…" : "Create deployment →"}</button></form>
      <div className="section-title"><h2>Deployment registry</h2><span>{snapshot.deployments.length} ENVIRONMENTS</span></div>
      {snapshot.deployments.length === 0 ? <EmptyState title="배포가 없습니다.">현재 Pipeline 버전을 Preview endpoint로 고정하세요.</EmptyState> : (
        <div className="deployment-list">
          {snapshot.deployments.map((deployment) => {
            const pipeline = snapshot.pipelines.find((item) => item.id === deployment.pipeline_id);
            const endpoint = `${API_BASE}/public/${deployment.slug}/chat`;
            return <article className="deployment-card" key={deployment.id}><div className="deployment-main"><header><div><span>DEPLOYMENT / {deployment.id.slice(0, 8)}</span><h2>{pipeline?.name ?? "Deleted pipeline"}</h2><p>VERSION {deployment.version} · {formatDate(deployment.created_at)}</p></div><StatusBadge tone={deployment.status === "production" ? "ok" : "preview"}>{deployment.status.toUpperCase()}</StatusBadge></header><div className="endpoint"><b>POST</b><code>{endpoint}</code><button onClick={() => void copy(endpoint)}>COPY</button></div></div><div className="deployment-aside"><span>IMMUTABLE POINTER</span><strong>v{deployment.version}</strong><small>/{deployment.slug}</small></div></article>;
          })}
        </div>
      )}
    </section>
  );
}
