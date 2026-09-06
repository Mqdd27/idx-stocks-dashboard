import type { ReactNode } from "react";

export type NewsItem = {
  symbol?: string;
  title: string;
  url?: string;
  source?: string;
  published_at?: string;
  summary?: string;
  sentiment?: string;
};

export function NewsList({
  rows,
  aggregate = false,
}: {
  rows: NewsItem[];
  aggregate?: boolean;
}) {
  if (!rows.length)
    return (
      <div className="empty-state card">Belum ada berita untuk filter ini.</div>
    );
  return (
    <div className="card">
      {rows.map((item, index) => (
        <article
          className="news-item"
          key={`${item.url || item.title}-${index}`}
        >
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="t"
          >
            {aggregate && (
              <span style={{ color: "var(--amber)" }}>[{item.symbol}] </span>
            )}
            {item.title}
          </a>
          <div className="m">
            {item.source || "Unknown"}
            {item.published_at
              ? " - " + new Date(item.published_at).toLocaleString("id-ID")
              : ""}
            {item.sentiment ? ` - ${item.sentiment.toUpperCase()}` : ""}
          </div>
          {item.summary && (
            <div className="muted" style={{ marginTop: 3 }}>
              {item.summary}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}

export function NewsError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="empty-state card">
      <b>NEWS FEED GAGAL DIMUAT</b>
      <span className="muted">{message}</span>
      <button className="btn" type="button" onClick={onRetry}>
        COBA LAGI
      </button>
    </div>
  );
}

export function NewsLoading({ children }: { children: ReactNode }) {
  return (
    <div className="empty-state">
      <span className="spin" /> {children}
    </div>
  );
}
