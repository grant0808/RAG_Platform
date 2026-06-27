"use client";

import { useState } from "react";

import { EmptyState, PageHeading, StatusBadge, formatDate } from "@/components/ui";
import { API_BASE, api } from "@/lib/api";
import type { AppSnapshot, Deployment, DeploymentEnvironment } from "@/lib/types";

export function DeploymentsView({
  snapshot,
  refresh,
  notify,
}: {
  snapshot: AppSnapshot;
  refresh: () => Promise<void>;
  notify: (message: string) => void;
}) {
  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function create(form: FormData) {
    setCreating(true);
    try {
      const deployment = await api.createDeployment(
        String(form.get("pipelineId")),
        String(form.get("slug") || ""),
        String(form.get("environment")) as DeploymentEnvironment,
      );
      notify(`${deployment.slug} deployment를 생성했습니다.`);
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Deployment 생성에 실패했습니다.");
    } finally {
      setCreating(false);
    }
  }

  async function copy(value: string) {
    await navigator.clipboard.writeText(value);
    notify("Endpoint를 복사했습니다.");
  }

  async function mutateDeployment(deployment: Deployment, action: () => Promise<unknown>) {
    setBusyId(deployment.id);
    try {
      await action();
      await refresh();
    } catch (caught) {
      notify(caught instanceof Error ? caught.message : "Deployment 변경에 실패했습니다.");
    } finally {
      setBusyId(null);
    }
  }

  async function changeEnvironment(deployment: Deployment, environment: DeploymentEnvironment) {
    await mutateDeployment(deployment, async () => {
      await api.updateDeployment(deployment.id, { environment });
      notify(`${deployment.slug} environment를 ${environment}로 변경했습니다.`);
    });
  }

  async function toggleRunning(deployment: Deployment) {
    await mutateDeployment(deployment, async () => {
      if (deployment.status === "running") {
        await api.stopDeployment(deployment.id);
        notify(`${deployment.slug} deployment를 중지했습니다.`);
      } else {
        await api.runDeployment(deployment.id);
        notify(`${deployment.slug} deployment를 실행했습니다.`);
      }
    });
  }

  async function deleteDeployment(deployment: Deployment) {
    if (!window.confirm(`/${deployment.slug} deployment를 삭제할까요?`)) return;
    await mutateDeployment(deployment, async () => {
      await api.deleteDeployment(deployment.id);
      notify(`${deployment.slug} deployment를 삭제했습니다.`);
    });
  }

  return (
    <section className="page">
      <PageHeading
        index="06"
        title="Deploy once."
        outline="Observe always."
        description="Deployment는 immutable pipeline version을 고정합니다. Draft를 바꿔도 public endpoint는 안정적으로 유지되며, 중지, 재실행, 삭제할 수 있습니다."
      />
      <form
        className="deployment-form"
        onSubmit={(event) => {
          event.preventDefault();
          void create(new FormData(event.currentTarget));
        }}
      >
        <label>
          <span>PIPELINE</span>
          <select name="pipelineId" required>
            {snapshot.pipelines.map((pipeline) => (
              <option key={pipeline.id} value={pipeline.id}>
                {pipeline.name} / v{pipeline.current_version}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>SLUG / OPTIONAL</span>
          <input name="slug" placeholder="support-bot" pattern="[a-zA-Z0-9-]+" minLength={3} maxLength={80} />
        </label>
        <label>
          <span>ENVIRONMENT</span>
          <select name="environment">
            <option value="preview">Preview</option>
            <option value="production">Production</option>
          </select>
        </label>
        <button className="button acid" disabled={creating || !snapshot.pipelines.length}>
          {creating ? "Deploying..." : "Create deployment"}
        </button>
      </form>
      <div className="section-title">
        <h2>Deployment registry</h2>
        <span>{snapshot.deployments.length} ENDPOINTS</span>
      </div>
      {snapshot.deployments.length === 0 ? (
        <EmptyState title="아직 deployment가 없습니다.">
          현재 pipeline version을 preview endpoint로 고정하세요.
        </EmptyState>
      ) : (
        <div className="deployment-list">
          {snapshot.deployments.map((deployment) => {
            const pipeline = snapshot.pipelines.find((item) => item.id === deployment.pipeline_id);
            const endpoint = `${API_BASE}/public/${deployment.slug}/chat`;
            const busy = busyId === deployment.id;
            return (
              <article className="deployment-card" key={deployment.id}>
                <div className="deployment-main">
                  <header>
                    <div>
                      <span>DEPLOYMENT / {deployment.id.slice(0, 8)}</span>
                      <h2>{pipeline?.name ?? "Deleted pipeline"}</h2>
                      <p>Version {deployment.version} / {formatDate(deployment.created_at)}</p>
                    </div>
                    <div className="deployment-badges">
                      <StatusBadge tone={deployment.environment === "production" ? "ok" : "preview"}>
                        {deployment.environment.toUpperCase()}
                      </StatusBadge>
                      <StatusBadge tone={deployment.status === "running" ? "ok" : "muted"}>
                        {deployment.status.toUpperCase()}
                      </StatusBadge>
                    </div>
                  </header>
                  <div className="endpoint">
                    <b>POST</b>
                    <code>{endpoint}</code>
                    <button onClick={() => void copy(endpoint)}>COPY</button>
                  </div>
                  <div className="deployment-actions">
                    <button className="button" disabled={busy} onClick={() => void toggleRunning(deployment)}>
                      {deployment.status === "running" ? "Stop" : "Run"}
                    </button>
                    <select
                      disabled={busy}
                      value={deployment.environment}
                      onChange={(event) =>
                        void changeEnvironment(deployment, event.target.value as DeploymentEnvironment)
                      }
                    >
                      <option value="preview">Preview</option>
                      <option value="production">Production</option>
                    </select>
                    <button className="button danger" disabled={busy} onClick={() => void deleteDeployment(deployment)}>
                      Delete
                    </button>
                  </div>
                </div>
                <div className="deployment-aside">
                  <span>IMMUTABLE POINTER</span>
                  <strong>v{deployment.version}</strong>
                  <small>/{deployment.slug}</small>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
