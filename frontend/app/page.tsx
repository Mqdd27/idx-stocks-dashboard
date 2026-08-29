"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmtNum, fmtVol, pct, cls } from "@/lib/format";
import { DataState, SectionHeading, TerminalMetric, TerminalPanel } from "@/components/Terminal";
import RecommendationBoard, { AIWatchlistWidget } from "@/components/RecommendationBoard";

export default function MarketPage() {
  const [data, setData] = useState<any>(null); const [watchlist, setWatchlist] = useState<any[]>([]); const [status, setStatus] = useState<any>(null); const [err, setErr] = useState(""); const [updated, setUpdated] = useState<Date | null>(null);
  const [flashes, setFlashes] = useState<Record<string, "up" | "down">>({}); const previous = useRef<Record<string, number>>({});
  useEffect(() => {
    let alive = true;
    const load = () => Promise.all([api.overview(), api.watchlist(), api.marketStatus()]).then(([market, watch, marketStatus]) => {
      const next: Record<string, "up" | "down"> = {};
      for (const rows of [market.gainers, market.losers, market.most_active, watch.data]) for (const row of rows || []) { const price = row.close ?? row.price?.close; const prior = previous.current[row.symbol]; if (price != null && prior != null && price !== prior) next[row.symbol] = price > prior ? "up" : "down"; if (price != null) previous.current[row.symbol] = price; }
      if (alive) { setData(market); setWatchlist(watch.data || []); setStatus(marketStatus); setFlashes(next); setUpdated(new Date()); setErr(""); }
    }).catch((e) => alive && setErr(e.message || "MARKET DATA UNAVAILABLE"));
    load(); const timer = setInterval(load, 30000); return () => { alive = false; clearInterval(timer); };
  }, []);
  if (err) return <div className="terminal-error"><strong>MARKET DATA UNAVAILABLE</strong><span>{err}</span><button className="btn" onClick={() => location.reload()}>RETRY</button></div>;
  if (!data) return <div className="terminal-loading">LOADING MARKET DATA<span>...</span></div>;
  const ihsg = data.ihsg?.price; const tone = ihsg?.change_pct > 0 ? "positive" : ihsg?.change_pct < 0 ? "negative" : "";
  return <div className="market-terminal-page">
    <SectionHeading eyebrow="IDX / MARKET MONITOR" title="INDONESIA EQUITY MARKET" meta={<><DataState state={status?.is_open ? "live" : "closed"}>{status?.is_open ? "LIVE" : status?.status || "CLOSED"}</DataState><span>LAST {updated?.toLocaleTimeString("id-ID", { hour12: false })}</span></>} />
    <div className="market-summary-grid">
      <TerminalPanel title="IHSG COMPOSITE" code="IDX"><div className="ihsg-monitor"><div><strong className={tone}>{ihsg ? fmtNum(ihsg.close) : "-"}</strong><span className={cls(ihsg?.change_pct)}>{ihsg?.change != null ? `${ihsg.change >= 0 ? "+" : ""}${fmtNum(ihsg.change)}` : "-"} &nbsp; {pct(ihsg?.change_pct)}</span></div><DataState state={ihsg?.is_live ? "live" : ihsg?.is_stale ? "delayed" : "closed"}>{ihsg?.is_live ? "LIVE PRICE" : ihsg?.is_stale ? "DELAYED" : "LAST CLOSE"}</DataState></div></TerminalPanel>
      <div className="market-metric-strip"><TerminalMetric label="TOTAL VOLUME" value={fmtVol(data.total_volume)} /><TerminalMetric label="UNIVERSE" value="IDX" meta={`${(data.gainers?.length || 0) + (data.losers?.length || 0)} movers`} /><TerminalMetric label="SESSION" value={status?.current_session || status?.status || "-"} tone={status?.is_open ? "positive" : "warning"} /><TerminalMetric label="NEXT OPEN" value={status?.next_market_open ? new Date(status.next_market_open).toLocaleString("id-ID", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short" }) : "-"} /></div>
    </div>
    <div className="market-workspace">
      <div className="market-main-panels">
        <div className="market-table-grid"><MarketTable title="TOP GAINERS" code="UP" rows={data.gainers} flashes={flashes} /><MarketTable title="TOP LOSERS" code="DN" rows={data.losers} flashes={flashes} /></div>
        <MarketTable title="MOST ACTIVE" code="VOL" rows={data.most_active} flashes={flashes} showVolume wide />
      </div>
      <TerminalPanel title="WATCHLIST MONITOR" code="MON"><WatchRows rows={watchlist} /></TerminalPanel>
    </div>
  </div>;
}

function MarketTable({ title, code, rows, flashes, showVolume, wide }: { title: string; code: string; rows: any[]; flashes: Record<string, "up" | "down">; showVolume?: boolean; wide?: boolean }) {
  return <TerminalPanel title={title} code={code} className={wide ? "wide-market-panel" : ""}><div className="table-scroll"><table className="dense-table"><thead><tr><th>CODE</th><th className="num">LAST</th><th className="num">CHG</th><th className="num">CHG%</th>{showVolume && <th className="num">VOLUME</th>}<th>TIME</th></tr></thead><tbody>{rows.map((r) => <tr key={r.symbol}><td><Link href={`/stock/${r.symbol}`} className="ticker-link">{r.symbol}</Link></td><td className={`num ${flashes[r.symbol] ? `flash-${flashes[r.symbol]}` : ""}`}>{fmtNum(r.close)}</td><td className={`num ${cls(r.change)}`}>{r.change == null ? "-" : `${r.change >= 0 ? "+" : ""}${fmtNum(r.change)}`}</td><td className={`num ${cls(r.change_pct)}`}>{pct(r.change_pct)}</td>{showVolume && <td className="num">{fmtVol(r.volume).replace(" lembar", "")}</td>}<td className="data-time">{r.date ? new Date(r.date).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }) : "-"}</td></tr>)}</tbody></table></div></TerminalPanel>;
}
function WatchRows({ rows }: { rows: any[] }) { return rows.length === 0 ? <div className="terminal-empty">NO WATCHLIST SYMBOLS</div> : <table className="dense-table watch-monitor"><thead><tr><th>CODE</th><th className="num">LAST</th><th className="num">%</th></tr></thead><tbody>{rows.slice(0, 12).map((r) => <tr key={r.symbol}><td><Link href={`/stock/${r.symbol}`} className="ticker-link">{r.symbol}</Link></td><td className="num">{fmtNum(r.price?.close)}</td><td className={`num ${cls(r.price?.change_pct)}`}>{pct(r.price?.change_pct)}</td></tr>)}</tbody></table>; }
