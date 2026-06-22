import type { ViewName } from "@/lib/types";

const navItems: Array<[ViewName, string, string]> = [
  ["overview", "01", "Overview"],
  ["sources", "02", "Data sources"],
  ["providers", "03", "Model providers"],
  ["pipeline", "04", "Pipeline studio"],
  ["playground", "05", "Playground"],
  ["deployments", "06", "Deployments"],
];

export function Sidebar({
  view,
  open,
  onNavigate,
}: {
  view: ViewName;
  open: boolean;
  onNavigate: (view: ViewName) => void;
}) {
  return (
    <aside className={`sidebar ${open ? "open" : ""}`}>
      <button className="brand" onClick={() => onNavigate("overview")} aria-label="Foundry 홈">
        <span className="brand-mark">F/</span>
        <span className="brand-word">FOUNDRY</span>
      </button>
      <nav className="main-nav" aria-label="주요 메뉴">
        {navItems.map(([id, index, label]) => (
          <button
            key={id}
            className={`nav-item ${view === id ? "active" : ""}`}
            onClick={() => onNavigate(id)}
          >
            <span className="nav-index">{index}</span>
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-foot">
        <div className="build-card">
          <span>LOCAL / POC</span>
          <strong>Auth disabled</strong>
          <small>외부 네트워크에 직접 공개하지 마세요.</small>
        </div>
        <div className="account-row">
          <span className="avatar">LC</span>
          <span>
            <strong>LangChain Lab</strong>
            <small>Developer workspace</small>
          </span>
        </div>
      </div>
    </aside>
  );
}
