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
        description="문서를 연결하고 RAG 파이프라인을 구성한 뒤, citation, trace, token 사용량까지 한 화면에서 검증합니다."
      />
      <div className="hero-grid">
        <article className="hero-card">
          <div className="hero-top">
            <StatusBadge>API CONNECTED</StatusBadge>
            <span>VERSION / {snapshot.health?.version}</span>
          </div>
          <div className="hero-copy">
            <span className="eyebrow">CONTROL ROOM / FIRST VALUE</span>
            <h2>
              질문에서 근거까지,
              <br />
              <em>하나의 local workbench에서.</em>
            </h2>
            <p>
              Bootstrap 데이터와 deterministic local model로 provider 비용 없이 전체 제품 흐름을 테스트할 수 있습니다.
            </p>
            <button className="button acid" onClick={() => onNavigate("playground")}>
              Open playground
            </button>
          </div>
        </article>
        <aside className="route-card">
          <div className="route-rail">
            <span className={snapshot.pipelines.length ? "active" : ""}>R</span>
          </div>
          <div className="route-detail">
            <span className="eyebrow">LANGCHAIN / COVERAGE</span>
            <h3>RAG strategy</h3>
            <p>
              Retriever와 chat model을 공통 응답 계약으로 묶어 citation, trace, token 사용량을 검증합니다.
            </p>
            <dl>
              <div>
                <dt>Sources</dt>
                <dd>{snapshot.sources.length}</dd>
              </div>
              <div>
                <dt>Chunks</dt>
                <dd>{chunks}</dd>
              </div>
              <div>
                <dt>Providers</dt>
                <dd>{snapshot.providers.length}</dd>
              </div>
            </dl>
          </div>
        </aside>
      </div>

      <div className="section-title">
        <h2>Local workspace</h2>
        <span>LIVE DATABASE</span>
      </div>
      <div className="metric-grid">
        <Metric label="PIPELINES" value={String(snapshot.pipelines.length)} detail="RAG 전략 활성" />
        <Metric label="KNOWLEDGE SOURCES" value={String(snapshot.sources.length)} detail={`${chunks}개 indexed chunks`} />
        <Metric label="DEPLOYMENTS" value={String(snapshot.deployments.length)} detail={`production ${production} / stopped ${stopped}`} />
        <Metric label="AUTH" value={snapshot.health?.auth_enabled ? "ON" : "OFF"} detail="local PoC mode" warning />
      </div>

      <div className="section-title">
        <h2>Pipeline registry</h2>
        <span>{snapshot.pipelines.length} TOTAL</span>
      </div>
      <div className="table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Pipeline</th>
              <th>Strategy</th>
              <th>Provider / Model</th>
              <th>Version</th>
              <th>Updated</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {snapshot.pipelines.map((pipeline) => (
              <tr key={pipeline.id}>
                <td>
                  <strong>{pipeline.name}</strong>
                </td>
                <td>
                  <span className={`strategy-label ${pipeline.strategy}`}>
                    {pipeline.strategy.toUpperCase()}
                  </span>
                </td>
                <td>
                  <span className="muted">
                    {pipeline.provider} / {pipeline.model}
                  </span>
                </td>
                <td>v{pipeline.current_version}</td>
                <td>{formatDate(pipeline.updated_at)}</td>
                <td>
                  <button
                    className="text-button"
                    onClick={() => {
                      onSelectPipeline(pipeline.id);
                      onNavigate("pipeline");
                    }}
                  >
                    Open
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Metric({
  label,
  value,
  detail,
  warning = false,
}: {
  label: string;
  value: string;
  detail: string;
  warning?: boolean;
}) {
  return (
    <article className={`metric ${warning ? "warning" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}
