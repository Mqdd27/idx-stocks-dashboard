"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { TerminalPanel } from "./Terminal";
import { fmtNum, fmtPrice, pct, cls } from "@/lib/format";

export default function RecommendationBoard() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { api.recommendationsToday().then(setData).catch(() => setData(null)); }, []);
  if (!data) return null;
  return <section className="recommendation-board">
    <div className="recommendation-head"><div><span className="terminal-eyebrow">DAILY RESEARCH</span><h2>TODAY'S TRADE IDEAS</h2></div><div className="terminal-page-meta"><span>MARKET {data.market?.status || "—"}</span><span>AS OF {data.generated_at ? new Date(data.generated_at).toLocaleTimeString("id-ID", { hour12: false }) : "—"}</span></div></div>
    <div className="recommendation-grid"><RecommendationPanel title="TRADINGAGENTS PICKS" code="TA" rows={data.trading_agents || []} consensus={data.consensus || {}} /><RecommendationPanel title="PAPER TRADE PICKS" code="QNT" rows={data.paper_trade || []} consensus={data.consensus || {}} /></div>
  </section>;
}
function RecommendationPanel({ title, code, rows, consensus }: { title: string; code: string; rows: any[]; consensus: Record<string, string> }) {
  return <TerminalPanel title={title} code={code}>{rows.length === 0 ? <div className="terminal-empty">NO QUALIFIED SETUP</div> : <div className="recommendation-list">{rows.map((r) => <article className="recommendation-row" key={`${r.method}-${r.symbol}-${r.strategy}`}><div className="recommendation-symbol"><Link href={`/stock/${r.symbol}`} className="ticker-link">{r.symbol}</Link><span>{r.strategy}</span></div><div className="recommendation-price"><span>LAST</span><strong>{fmtPrice(r.current_price)}</strong><span className={cls(r.action === "BUY" ? 1 : -1)}>{r.action}</span></div><div className="recommendation-levels"><span>ENTRY <b>{fmtPrice(r.entry_low)}–{fmtPrice(r.entry_high)}</b></span><span>TP1 <b className="positive">{fmtPrice(r.tp1)}</b></span><span>TP2 <b className="positive">{fmtPrice(r.tp2)}</b></span><span>SL <b className="negative">{fmtPrice(r.stop_loss)}</b></span><span>R/R <b>{r.risk_reward ? Number(r.risk_reward).toFixed(2) : "—"}</b></span><span>SCORE <b>{r.score ?? "—"}</b></span><span>CONSENSUS <b>{consensus[r.symbol] || "NOT ANALYZED"}</b></span></div><div className="recommendation-why">{(r.reasons?.positive || []).map((x: string) => <span key={x} className="positive">+ {x}</span>)}{(r.reasons?.negative || []).map((x: string) => <span key={x} className="negative">− {x}</span>)}</div></article>)}</div>}
  </TerminalPanel>;
}


export function AIWatchlistWidget() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { api.aiWatchlistToday().then(setData).catch(() => setData(null)); }, []);
  if (!data) return null;
  return <TerminalPanel title="AI WATCHLIST" code="WATCH" actions={<Link href="/ai-watchlist" className="ticker-link">VIEW ALL</Link>}>
    {data.data?.length ? <table className="dense-table"><thead><tr><th>CODE</th><th>METHOD</th><th>STATUS</th><th className="num">SCORE</th></tr></thead><tbody>{data.data.slice(0, 6).map((r: any) => <tr key={`${r.method}-${r.symbol}`}><td><Link href={`/stock/${r.symbol}`} className="ticker-link">{r.symbol}</Link></td><td>{r.method === "TRADING_AGENTS" ? "TA" : "PAPER"}</td><td>{r.status}</td><td className="num">{r.score ?? "-"}</td></tr>)}</tbody></table> : <div className="terminal-empty">NO QUALIFIED WATCHLIST CANDIDATES</div>}
  </TerminalPanel>;
}
