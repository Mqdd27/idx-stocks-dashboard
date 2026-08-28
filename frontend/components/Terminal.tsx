import type { ReactNode } from "react";

export function TerminalPanel({ title, code, actions, children, className = "" }: { title: string; code?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`terminal-panel ${className}`}>
    <header className="terminal-panel-head">
      <div><span className="terminal-panel-code">{code || "//"}</span><h2>{title}</h2></div>
      {actions && <div className="terminal-panel-actions">{actions}</div>}
    </header>
    <div className="terminal-panel-body">{children}</div>
  </section>;
}

export function TerminalMetric({ label, value, tone = "", meta }: { label: string; value: ReactNode; tone?: "positive" | "negative" | "warning" | ""; meta?: ReactNode }) {
  return <div className="terminal-metric">
    <span className="terminal-metric-label">{label}</span>
    <strong className={`terminal-metric-value ${tone}`}>{value}</strong>
    {meta && <span className="terminal-metric-meta">{meta}</span>}
  </div>;
}

export function DataState({ state, children }: { state: "live" | "delayed" | "closed" | "error"; children: ReactNode }) {
  return <span className={`data-state ${state}`}><i />{children}</span>;
}

export function SectionHeading({ eyebrow, title, meta, actions }: { eyebrow?: string; title: string; meta?: ReactNode; actions?: ReactNode }) {
  return <div className="terminal-page-head">
    <div>{eyebrow && <span className="terminal-eyebrow">{eyebrow}</span>}<h1>{title}</h1>{meta && <div className="terminal-page-meta">{meta}</div>}</div>
    {actions && <div className="terminal-page-actions">{actions}</div>}
  </div>;
}
