import { PageHeading, StatusBadge, formatDate } from "@/components/ui";
import type { AppSnapshot, ViewName } from "@/lib/types";

export function OverviewView({
  snapshot,
  onNavigate,
  onSelectPipeline,
}: {
  snapshot: AppSnapshot;
  refresh: () => Promise<void>;
  notify: (message: string) => void;
  onNavigate: (view: ViewName) => void;
  onSelectPipeline: (id: string) => void;
}) {
  const strategies = new Set(snapshot.pipelines.map((pipeline) => pipeline.strategy));
  const chunks = snapshot.sources.reduce((total, source) => total + source.chunk_count, 0);
  const production = snapshot.deployments.filter(
    (item) => item.environment === "production",
  ).length;
  const stopped = snapshot.deployments.filter((item) => item.status === "stopped").length;

  return (
    <section className="page">
      <PageHeading
        index="01"
        title="Build knowledge."
        outline="Ship answers."
        description="문서와 테이블을 실제 LangChain 실행 경로에 연결하고, 근거와 trace가 남는 답변으로 검증하세요."
      />
      <div className="hero-grid">
        <article className="hero-card">
          <div className="hero-top">
            <StatusBadge>API CONNECTED</StatusBadge>
            <span>VERSION / {snapshot.health?.version}</span>
          </div>
          <div className="hero-copy">
            <span className="eyebrow">FIRST VALUE / UNDER 10 MIN</span>
            <h2>질문에서 근거까지,<br /><em>하나의 실행 흐름.</em></h2>
            <p>로컬 DB와 fake model이 준비되어 있어 외부 비용 없이 전체 퍼널을 시험할 수 있습니다.</p>
            <button className="button acid" onClick={() => onNavigate("playground")}>Open playground →</button>
          </div>
        </article>
        <aside className="route-card">
          <div className="route-rail">
            {(["R", "T", "C"] as const).map((letter, index) => (
              <span key={letter} className={strategies.has((["rag", "tag", "cag"] as const)[index]) ? "active" : ""}>{letter}</span>
            ))}
          </div>
          <div className="route-detail">
            <span className="eyebrow">LANGCHAIN / COVERAGE</span>
            <h3>{strategies.size} / 3 strategies</h3>
            <p>Runnable, Retriever, Safe SQL Tool, cache fallback을 동일한 응답 계약으로 비교합니다.</p>
            <dl>
              <div><dt>Sources</dt><dd>{snapshot.sources.length}</dd></div>
              <div><dt>Chunks</dt><dd>{chunks}</dd></div>
              <div><dt>Providers</dt><dd>{snapshot.providers.length}</dd></div>
            </dl>
          </div>
        </aside>
      </div>

      <div className="section-title"><h2>로컬 워크스페이스</h2><span>LIVE DATABASE</span></div>
      <div className="metric-grid">
        <Metric label="PIPELINES" value={String(snapshot.pipelines.length)} detail={`${strategies.size} strategy types`} />
        <Metric label="KNOWLEDGE SOURCES" value={String(snapshot.sources.length)} detail={`${chunks} indexed chunks`} />
        <Metric
          label="DEPLOYMENTS"
          value={String(snapshot.deployments.length)}
          detail={`${production} production · ${stopped} stopped`}
        />
        <Metric label="AUTH" value={snapshot.health?.auth_enabled ? "ON" : "OFF"} detail="PoC local only" warning />
      </div>

      <div className="section-title"><h2>파이프라인 레지스트리</h2><span>{snapshot.pipelines.length} TOTAL</span></div>
      <div className="table-card">
        <table className="data-table">
          <thead><tr><th>Pipeline</th><th>Strategy</th><th>Provider / Model</th><th>Version</th><th>Updated</th><th /></tr></thead>
          <tbody>
            {snapshot.pipelines.map((pipeline) => (
              <tr key={pipeline.id}>
                <td><strong>{pipeline.name}</strong></td>
                <td><span className={`strategy-tag ${pipeline.strategy}`}>{pipeline.strategy.toUpperCase()}</span></td>
                <td><span className="muted">{pipeline.provider} / {pipeline.model}</span></td>
                <td>v{pipeline.current_version}</td>
                <td>{formatDate(pipeline.updated_at)}</td>
                <td><button className="text-button" onClick={() => { onSelectPipeline(pipeline.id); onNavigate("pipeline"); }}>Open →</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Metric({ label, value, detail, warning = false }: { label: string; value: string; detail: string; warning?: boolean }) {
  return <article className={`metric ${warning ? "warning" : ""}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}
