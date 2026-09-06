"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";

type Row = any;

export default function AIWatchlistPage() {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = () =>
    api
      .aiWatchlistToday()
      .then(setData)
      .catch((caught) => setError(caught.message));
  usePolling(load, 30000);

  const refresh = async () => {
    setBusy(true);
    setError("");
    try {
      await api.aiWatchlistRefresh();
      await load();
    } catch (caught: any) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };
  const rows = data?.data || [];
  const agents = rows.filter((row: Row) => row.method === "TRADING_AGENTS");
  const paper = rows.filter((row: Row) => row.method === "PAPER_TRADE");

  return (
    <div>
      <div className="terminal-page-head">
        <div>
          <span className="terminal-eyebrow">MONITOR / DAILY SETUPS</span>
          <h1>AI WATCHLIST</h1>
          <div className="terminal-page-meta">
            <span>TRADING DAY {data?.trading_date || "-"}</span>
            <span>MARKET {data?.market?.status || "-"}</span>
            <span>
              DATA AS OF{" "}
              {data?.generated_at
                ? new Date(data.generated_at).toLocaleTimeString("id-ID", {
                    hour12: false,
                  })
                : "-"}
            </span>
          </div>
        </div>
        <button className="btn" onClick={refresh} disabled={busy}>
          {busy ? "UPDATING…" : "REFRESH"}
        </button>
      </div>
      {error && (
        <div className="analysis-err">WATCHLIST UPDATE FAILED · {error}</div>
      )}
      <div className="watchlist-overview">
        <Summary title="TOP AI WATCHLIST" rows={rows} />
        <Summary title="METHOD OVERLAP" rows={overlap(rows)} />
      </div>
      <WatchSection title="TRADINGAGENTS WATCHLIST" code="TA" rows={agents} />
      <WatchSection title="PAPER TRADE WATCHLIST" code="QNT" rows={paper} />
    </div>
  );
}

function overlap(rows: Row[]) {
  const grouped = new Map<string, Row[]>();
  rows.forEach((row) =>
    grouped.set(row.symbol, [...(grouped.get(row.symbol) || []), row]),
  );
  return [...grouped.entries()]
    .filter(([, items]) => items.length > 1)
    .map(([symbol, items]) => ({
      ...items[0],
      symbol,
      status: "DUAL SIGNAL",
      score: items
        .map((item) => item.score)
        .filter(Boolean)
        .join(" / "),
      reasons: { positive: ["TradingAgents + Paper Engine"] },
    }));
}

function Summary({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <div className="terminal-panel">
      <header className="terminal-panel-head">
        <div>
          <span className="terminal-panel-code">AI</span>
          <h2>{title}</h2>
        </div>
      </header>
      {rows.length ? (
        <table className="dense-table">
          <tbody>
            {rows.slice(0, 6).map((row) => (
              <tr key={`${row.method}-${row.symbol}`}>
                <td>
                  <Link href={`/stock/${row.symbol}`} className="ticker-link">
                    {row.symbol}
                  </Link>
                </td>
                <td>{row.method === "TRADING_AGENTS" ? "TA" : "PAPER"}</td>
                <td>{row.status}</td>
                <td className="num">{row.score ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="terminal-empty">NO QUALIFIED WATCHLIST CANDIDATES</div>
      )}
    </div>
  );
}

function WatchSection({
  title,
  code,
  rows,
}: {
  title: string;
  code: string;
  rows: Row[];
}) {
  return (
    <div className="terminal-panel watch-section">
      <header className="terminal-panel-head">
        <div>
          <span className="terminal-panel-code">{code}</span>
          <h2>{title}</h2>
        </div>
      </header>
      {rows.length ? (
        <div className="table-scroll">
          <table className="dense-table">
            <thead>
              <tr>
                <th>CODE</th>
                <th className="num">LAST</th>
                <th>STATUS</th>
                <th className="num">ENTRY ZONE</th>
                <th className="num">TP1</th>
                <th className="num">SL</th>
                <th className="num">R/R</th>
                <th>WHY WATCH</th>
                <th>DATA AS OF</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <Link href={`/stock/${row.symbol}`} className="ticker-link">
                      {row.symbol}
                    </Link>
                  </td>
                  <td className="num">{formatPrice(row.last_price)}</td>
                  <td>{row.status}</td>
                  <td className="num">
                    {formatPrice(row.entry_low)}–{formatPrice(row.entry_high)}
                  </td>
                  <td className="num pos">{formatPrice(row.tp1)}</td>
                  <td className="num neg">{formatPrice(row.stop_loss)}</td>
                  <td className="num">
                    {row.risk_reward ? Number(row.risk_reward).toFixed(2) : "-"}
                  </td>
                  <td>
                    {(row.reasons?.positive || []).join(" · ") ||
                      "Setup sedang dipantau"}
                  </td>
                  <td className="data-time">
                    {row.data_timestamp
                      ? new Date(row.data_timestamp).toLocaleTimeString(
                          "id-ID",
                          { hour12: false },
                        )
                      : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="terminal-empty">NO QUALIFIED WATCHLIST CANDIDATES</div>
      )}
    </div>
  );
}

function formatPrice(value: unknown) {
  return value == null
    ? "-"
    : Math.round(Number(value)).toLocaleString("id-ID");
}
