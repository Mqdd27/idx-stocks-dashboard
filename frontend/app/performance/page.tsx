"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const methods = [["", "ALL"], ["TRADING_AGENTS", "TRADINGAGENTS"], ["PAPER_TRADE", "PAPER TRADE"]];
const periods = [["daily", "DAILY"], ["weekly", "WEEKLY"], ["monthly", "MONTHLY"], ["yearly", "YEARLY"]];

function percent(value: number | null | undefined) { return value == null ? "N/A" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`; }
function value(row: any, key: string) { return row?.[key] ?? "—"; }

export default function PerformancePage() {
  const [strategy, setStrategy] = useState("BSJP");
  const [period, setPeriod] = useState("daily");
  const [method, setMethod] = useState("");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null); setError("");
    api.strategyPerformance(strategy, period, method || undefined).then(setData).catch(() => setError("Performance API unavailable."));
  }, [strategy, period, method]);

  const combined = data?.combined || {};
  const rows = data?.data || [];
  const activeRows = method ? rows : rows.filter((row: any) => ["TRADING_AGENTS", "PAPER_TRADE"].includes(row.method));

  return <div>
    <h1 className="page-title">STRATEGY PERFORMANCE</h1>
    <div className="tabs">{["BSJP", "BPJS"].map((item) => <button className={strategy === item ? "active" : ""} onClick={() => setStrategy(item)} key={item}>{item}</button>)}</div>
    <div className="tabs">{periods.map(([id, label]) => <button className={period === id ? "active" : ""} onClick={() => setPeriod(id)} key={id}>{label}</button>)}</div>
    <div className="tabs">{methods.map(([id, label]) => <button className={method === id ? "active" : ""} onClick={() => setMethod(id)} key={id}>{label}</button>)}</div>
    {error && <div className="terminal-error">{error}</div>}
    {!data && !error && <div className="terminal-loading"><span>LOADING PERFORMANCE DATA</span></div>}
    {data && <>
      <p className="data-time">PERIOD {data.period_start} — {data.period_end} · CALCULATED {new Date(data.generated_at).toLocaleString("id-ID", { timeZone: "Asia/Jakarta" })}</p>
      <div className="grid grid-2">
        <Metric title="TRADES" value={combined.trades ?? 0} />
        <Metric title="WIN RATE" value={combined.win_rate == null ? "N/A" : `${combined.win_rate.toFixed(2)}%`} />
        <Metric title="NET RETURN" value={percent(combined.net_return_pct)} tone={combined.net_return_pct} />
        <Metric title="PROFIT FACTOR" value={combined.profit_factor ?? "N/A"} />
        <Metric title="AVG RETURN / TRADE" value={percent(combined.average_return_pct)} tone={combined.average_return_pct} />
        <Metric title="STATUS" value={combined.sample_quality || combined.status || "—"} />
      </div>
      <div className="card">
        <div className="card-title">METHOD COMPARISON</div>
        <div className="table-scroll"><table className="dense-table"><thead><tr><th>METRIC</th>{activeRows.map((row: any) => <th className="num" key={row.method}>{row.method === "TRADING_AGENTS" ? "TRADINGAGENTS" : "PAPER TRADE"}</th>)}</tr></thead><tbody>
          <TableRow label="Trades" rows={activeRows} field="trades" />
          <TableRow label="Win Rate" rows={activeRows} field="win_rate" format={(v: any) => v == null ? "N/A" : `${v.toFixed(2)}%`} />
          <TableRow label="Net Return" rows={activeRows} field="net_return_pct" format={percent} />
          <TableRow label="Profit Factor" rows={activeRows} field="profit_factor" />
          <TableRow label="Avg Return" rows={activeRows} field="average_return_pct" format={percent} />
          <TableRow label="Best / Worst" rows={activeRows} format={(v: any, row: any) => `${percent(row.best_trade_pct)} / ${percent(row.worst_trade_pct)}`} />
        </tbody></table></div>
      </div>
      <div className="card">
        <div className="card-title">EXECUTION SUMMARY</div>
        <div className="table-scroll"><table className="dense-table"><thead><tr><th>METHOD</th><th className="num">SIGNALS</th><th className="num">TRIGGERED</th><th className="num">WINS</th><th className="num">LOSSES</th><th className="num">BREAKEVEN</th><th className="num">OPEN</th><th className="num">NOT TRIGGERED</th>{strategy === "BPJS" && <th className="num">ANOMALIES</th>}</tr></thead><tbody>{activeRows.map((row: any) => <tr key={row.method}><td>{row.method === "TRADING_AGENTS" ? "TRADINGAGENTS" : "PAPER TRADE"}</td><td className="num">{value(row, "signals")}</td><td className="num">{value(row, "triggered")}</td><td className="num pos">{value(row, "winning_trades")}</td><td className="num neg">{value(row, "losing_trades")}</td><td className="num">{value(row, "breakeven_trades")}</td><td className="num">{value(row, "open_positions")}</td><td className="num">{value(row, "not_triggered")}</td>{strategy === "BPJS" && <td className="num neg">{value(row, "anomalies")}</td>}</tr>)}</tbody></table></div>
        {combined.trades === 0 && <p className="terminal-empty">NO COMPLETED {strategy} TRADES FOR THIS PERIOD</p>}
      </div>
    </>}
  </div>;
}

function Metric({ title, value, tone }: { title: string; value: string | number; tone?: number }) { return <div className="card"><div className="muted">{title}</div><strong className={`metric-value ${tone == null ? "" : tone >= 0 ? "pos" : "neg"}`}>{value}</strong></div>; }
function TableRow({ label, rows, field, format = (v: any) => v }: { label: string; rows: any[]; field?: string; format?: (v: any, row: any) => string | number }) { return <tr><td>{label}</td>{rows.map((row) => <td className="num" key={row.method}>{format(field ? row[field] : null, row)}</td>)}</tr>; }
