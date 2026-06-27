import type { ReactNode } from "react";

export function PageHeading({
  index,
  title,
  outline,
  description,
  action,
}: {
  index: string;
  title: string;
  outline: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <div className="eyebrow">{index} / FOUNDRY WORKBENCH</div>
        <h1>
          {title} <span className="outline">{outline}</span>
        </h1>
      </div>
      <div>
        <p>{description}</p>
        {action}
      </div>
    </header>
  );
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty-state">
      <span className="empty-mark">--</span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function StatusBadge({ children, tone = "ok" }: { children: ReactNode; tone?: string }) {
  return <span className={`status-badge ${tone}`}>{children}</span>;
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span className="spinner" role="status">
      <i /> {label}
    </span>
  );
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
