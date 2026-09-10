"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtVol } from "@/lib/format";

const PERIODS = ["1d", "5d", "20d", "1m", "3m"];

export default function ForeignFlowPage() {
  const [period, setPeriod] = useState("5d");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null); setError("");
    api.foreignFlow(period).then(setData).catch((caught) => setError(caught.message));
  }, [period]);

  if (error) return <div><h1 className="page-title">FOREIGN FLOW</h1><div className="terminal-error">FOREIGN FLOW UNAVAILABLE · {error}</div></div>;
  if (!data) return <div><h1 className="page-title">FOREIGN FLOW</h1><div className="terminal-loading">LOADING EOD FOREIGN FLOW…</div></div>;
  return <div><div className="terminal-page-head"><div><h1 className="page-title">FOREIGN FLOW</h1><span className="muted">EOD VOLUME DATA · IDX GETSTOCKSUMMARY · DATA THROUGH {data.market_date || "—"}</span></div></div><div className="tabs">{PERIODS.map((item) => <button key={item} className={period === item ? "active" : ""} onClick={() => setPeriod(item)}>{item.toUpperCase()}</button>)}</div><p className="muted">Foreign buy/sell adalah volume saham eksplisit dari IDX. Positif = FOREIGN NET BUY; negatif = FOREIGN NET SELL.</p><FlowTable title="TOP FOREIGN NET BUY" rows={data.top_buy} /><FlowTable title="TOP FOREIGN NET SELL" rows={data.top_sell} sell /></div>;
}

function FlowTable({ title, rows, sell = false }: { title: string; rows: any[]; sell?: boolean }) {
  return <section className="terminal-panel" style={{ marginTop: 12 }}><header className="terminal-panel-head"><div><span className="terminal-panel-code">{sell ? "SELL" : "BUY"}</span><h2>{title}</h2></div></header>{rows.length ? <div className="table-scroll"><table className="dense-table"><thead><tr><th>#</th><th>SYMBOL</th><th className="num">FOREIGN BUY</th><th className="num">FOREIGN SELL</th><th className="num">NET FOREIGN</th><th className="num">RATIO</th><th className="num">STREAK</th><th>STATUS</th></tr></thead><tbody>{rows.map((row: any, index: number) => <tr key={row.symbol}><td>{index + 1}</td><td><Link className="ticker-link" href={`/stock/${row.symbol}`}>{row.symbol}</Link></td><td className="num">{fmtVol(row.foreign_buy_volume)}</td><td className="num">{fmtVol(row.foreign_sell_volume)}</td><td className={`num ${row.net_foreign_volume > 0 ? "pos" : "neg"}`}>{row.net_foreign_volume > 0 ? "+" : ""}{fmtVol(row.net_foreign_volume)}</td><td className="num">{row.net_foreign_ratio == null ? "—" : `${row.net_foreign_ratio.toFixed(2)}%`}</td><td className={`num ${row.streak > 0 ? "pos" : row.streak < 0 ? "neg" : ""}`}>{row.streak > 0 ? "+" : ""}{row.streak}</td><td className={row.net_foreign_volume > 0 ? "pos" : "neg"}>{row.status}</td></tr>)}</tbody></table></div> : <div className="terminal-empty">NO FOREIGN FLOW DATA FOR THIS PERIOD</div>}</section>;
}
