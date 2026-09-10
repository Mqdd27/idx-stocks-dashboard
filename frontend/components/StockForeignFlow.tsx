"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtVol } from "@/lib/format";

export default function StockForeignFlow({ symbol }: { symbol: string }) {
  const [period, setPeriod] = useState("5d");
  const [data, setData] = useState<any>(null);

  useEffect(() => { setData(null); api.foreignFlowStock(symbol, period).then(setData).catch(() => setData({ data: null, history: [] })); }, [symbol, period]);
  if (!data) return <div className="terminal-loading">LOADING FOREIGN FLOW…</div>;
  if (!data.data) return <div className="terminal-empty">NO FOREIGN FLOW DATA · IDX EOD DATA NOT COLLECTED FOR THIS STOCK</div>;
  const flow = data.data;
  return <div><div className="tabs">{["1d", "5d", "20d", "1m", "3m"].map((item) => <button key={item} className={period === item ? "active" : ""} onClick={() => setPeriod(item)}>{item.toUpperCase()}</button>)}</div><p className="data-time">IDX EOD VOLUME · DATA THROUGH {String(flow.trading_date)} · {flow.status}</p><div className="stat-strip"><Stat label="FOREIGN BUY" value={fmtVol(flow.foreign_buy_volume)} /><Stat label="FOREIGN SELL" value={fmtVol(flow.foreign_sell_volume)} /><Stat label="NET FOREIGN" value={`${flow.net_foreign_volume > 0 ? "+" : ""}${fmtVol(flow.net_foreign_volume)}`} tone={flow.net_foreign_volume > 0 ? "pos" : "neg"} /><Stat label="NET RATIO" value={flow.net_foreign_ratio == null ? "—" : `${flow.net_foreign_ratio.toFixed(2)}%`} /><Stat label="STREAK" value={`${flow.streak > 0 ? "+" : ""}${flow.streak} sessions`} tone={flow.streak > 0 ? "pos" : flow.streak < 0 ? "neg" : ""} /><Stat label="STATUS" value={flow.status} tone={flow.net_foreign_volume > 0 ? "pos" : "neg"} /></div><div className="card"><div className="card-title">FOREIGN FLOW HISTORY · VOLUME</div><div className="table-scroll"><table className="dense-table"><thead><tr><th>DATE</th><th className="num">BUY</th><th className="num">SELL</th><th className="num">NET</th><th className="num">CUMULATIVE</th><th className="num">RATIO</th></tr></thead><tbody>{data.history.map((row: any) => <tr key={row.date}><td>{String(row.date)}</td><td className="num">{fmtVol(row.foreign_buy_volume)}</td><td className="num">{fmtVol(row.foreign_sell_volume)}</td><td className={`num ${row.net_foreign_volume > 0 ? "pos" : "neg"}`}>{row.net_foreign_volume > 0 ? "+" : ""}{fmtVol(row.net_foreign_volume)}</td><td className={`num ${row.cumulative_net_foreign_volume > 0 ? "pos" : "neg"}`}>{row.cumulative_net_foreign_volume > 0 ? "+" : ""}{fmtVol(row.cumulative_net_foreign_volume)}</td><td className="num">{row.net_foreign_ratio == null ? "—" : `${row.net_foreign_ratio.toFixed(2)}%`}</td></tr>)}</tbody></table></div></div></div>;
}

function Stat({ label, value, tone = "" }: { label: string; value: string; tone?: string }) { return <div className="stat"><div className="label">{label}</div><div className={`value ${tone}`}>{value}</div></div>; }
