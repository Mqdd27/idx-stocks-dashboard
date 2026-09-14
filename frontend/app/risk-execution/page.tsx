"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtNum, fmtPrice } from "@/lib/format";

export default function RiskExecutionPage() {
  const [summary, setSummary] = useState<any>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [decisions, setDecisions] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);

  const load = () =>
    Promise.all([api.riskSummary(), api.tradePlans(), api.riskDecisions()])
      .then(([nextSummary, nextPlans, nextDecisions]) => {
        setSummary(nextSummary);
        setPlans(nextPlans.data || []);
        setDecisions(nextDecisions.data || []);
        setError("");
      })
      .catch((err) => setError(err.message || "Risk data unavailable"));

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 15000);
    return () => window.clearInterval(timer);
  }, []);

  async function sync() {
    setSyncing(true);
    try {
      await api.riskSync();
      await load();
    } catch (err: any) {
      setError(err.message || "Shadow sync failed");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div>
      <div className="auto-trade-head">
        <div>
          <h1 className="page-title">RISK &amp; EXECUTION</h1>
          <p className="muted">Deterministic risk review and trade planning. Paper execution remains unchanged.</p>
        </div>
        <div className="paper-label">SHADOW MODE</div>
      </div>
      {error && <div className="terminal-error">{error}</div>}
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-title">ROLLOUT STATUS</div>
        <p className="muted">Risk decisions are recorded for active recommendations. No plan on this page can open a paper position yet.</p>
        <button className="btn btn-primary" disabled={syncing} onClick={sync}>{syncing ? "SYNCING…" : "SYNC SHADOW PLANS"}</button>
      </div>
      <div className="grid grid-4 auto-summary">
        <Metric label="MODE" value={summary?.mode || "SHADOW"} />
        <Metric label="PROPOSALS" value={summary?.total_proposals ?? "-"} />
        <Metric label="APPROVED" value={summary?.approval_count ?? "-"} tone="pos" />
        <Metric label="REJECTED" value={summary?.rejection_count ?? "-"} tone="neg" />
      </div>
      <div className="card" style={{ marginTop: 14 }}>
        <div className="card-title">PENDING TRADE PLANS</div>
        {!plans.length ? <div className="terminal-empty">NO SHADOW TRADE PLANS YET</div> : (
          <div className="table-scroll"><table className="dense-table"><thead><tr><th>SYMBOL</th><th>STRATEGY</th><th>METHOD</th><th>RISK</th><th className="num">ENTRY</th><th className="num">TP1</th><th className="num">SL</th><th className="num">R/R</th><th className="num">LOTS</th><th className="num">MAX LOSS</th><th /></tr></thead><tbody>
            {plans.map((plan) => <tr key={plan.id}><td className="sym-badge">{plan.symbol}</td><td>{plan.strategy}</td><td>{plan.method}</td><td className={plan.risk_decision?.decision === "APPROVE" ? "pos" : "neg"}>{plan.risk_decision?.decision}</td><td className="num">{fmtPrice(plan.entry_price)}</td><td className="num">{fmtPrice(plan.tp1)}</td><td className="num">{fmtPrice(plan.stop_loss)}</td><td className="num">{fmtNum(plan.risk_reward_ratio)}</td><td className="num">{plan.position_size_lots}</td><td className="num">{fmtNum(plan.expected_risk)}</td><td><button className="btn" onClick={() => setSelected(plan)}>DETAIL</button></td></tr>)}
          </tbody></table></div>
        )}
      </div>
      <div className="card" style={{ marginTop: 14 }}>
        <div className="card-title">LATEST RISK DECISIONS</div>
        {!decisions.length ? <div className="terminal-empty">NO RISK DECISIONS YET</div> : <div className="table-scroll"><table className="dense-table"><thead><tr><th>SYMBOL</th><th>STRATEGY</th><th>METHOD</th><th>DECISION</th><th>REASON CODES</th><th className="num">LOTS</th><th className="num">R/R</th></tr></thead><tbody>{decisions.map((decision) => <tr key={decision.id}><td className="sym-badge">{decision.proposal?.symbol || "-"}</td><td>{decision.proposal?.strategy || "-"}</td><td>{decision.proposal?.method || "-"}</td><td className={decision.decision === "APPROVE" ? "pos" : decision.decision === "REDUCE" ? "warning" : "neg"}>{decision.decision}</td><td>{decision.reason_codes?.join(", ") || "HARD LIMITS PASSED"}</td><td className="num">{decision.position_size_lots}</td><td className="num">{fmtNum(decision.risk_reward_ratio)}</td></tr>)}</tbody></table></div>}
      </div>
      {selected && <PlanDetail plan={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function Metric({ label, value, tone = "" }: { label: string; value: any; tone?: string }) {
  return <div className="stat"><div className="label">{label}</div><div className={`value ${tone}`}>{String(value)}</div></div>;
}

function PlanDetail({ plan, onClose }: { plan: any; onClose: () => void }) {
  const decision = plan.risk_decision || {};
  const proposal = plan.proposal || {};
  return <div className="card" style={{ marginTop: 14 }}>
    <div className="auto-trade-head"><div><div className="card-title">{plan.symbol} · TRADE PLAN #{plan.id}</div><p className="muted">Paper-only shadow record. No execution action is available.</p></div><button className="btn" onClick={onClose}>CLOSE</button></div>
    <div className="grid grid-4"><Metric label="RISK DECISION" value={decision.decision || "-"} tone={decision.decision === "APPROVE" ? "pos" : "neg"} /><Metric label="PORTFOLIO EXPOSURE" value={fmtNum(decision.portfolio_exposure_after)} /><Metric label="RISK AMOUNT" value={fmtNum(decision.risk_amount)} /><Metric label="LOTS" value={decision.position_size_lots || 0} /></div>
    <div className="grid grid-2" style={{ marginTop: 14 }}><div><div className="card-title">RISK REASONS</div>{decision.reason_codes?.length ? decision.reason_codes.map((code: string) => <div className="neg" key={code}>{code}</div>) : <div className="pos">HARD LIMITS PASSED</div>}{decision.warnings?.map((warning: string) => <div className="muted" key={warning}>{warning}</div>)}</div><div><div className="card-title">AUDIT</div><table><tbody><tr><td className="muted">Recommendation</td><td>#{proposal.recommendation_id || "-"}</td></tr><tr><td className="muted">Analysis</td><td>{proposal.analysis_id ? `#${proposal.analysis_id}` : "—"}</td></tr><tr><td className="muted">Foreign flow</td><td>{proposal.foreign_flow_context?.status || "NO DATA"}</td></tr><tr><td className="muted">Data type</td><td>{proposal.foreign_flow_context?.data_type || "—"}</td></tr></tbody></table></div></div>
  </div>;
}
