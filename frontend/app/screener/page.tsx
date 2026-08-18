"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmtNum, fmtVol, pct, cls } from "@/lib/format";

interface Filters {
  per_max: string; pbv_max: string; roe_min: string; roa_min: string; der_max: string;
  revenue_growth_min: string; net_income_growth_min: string; dividend_yield_min: string;
  volume_min: string; price_min: string; price_max: string; rsi_min: string; rsi_max: string;
  above_sma200: string;
}

const EMPTY: Filters = {
  per_max: "", pbv_max: "", roe_min: "", roa_min: "", der_max: "",
  revenue_growth_min: "", net_income_growth_min: "", dividend_yield_min: "",
  volume_min: "", price_min: "", price_max: "", rsi_min: "", rsi_max: "", above_sma200: "",
};

export default function ScreenerPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [rows, setRows] = useState<any[]>([]);
  const [ran, setRan] = useState(false);
  const [busy, setBusy] = useState(false);

  function set(field: keyof Filters, value: string) {
    setFilters((f) => ({ ...f, [field]: value }));
  }

  async function run() {
    setBusy(true);
    const params = new URLSearchParams();
    (Object.keys(filters) as (keyof Filters)[]).forEach((k) => {
      const v = filters[k].trim();
      if (v !== "") params.set(k, v);
    });
    try {
      const r = await api.screener(params);
      setRows(r.data);
      setRan(true);
    } catch (e: any) {
      alert("Screener gagal: " + e.message);
    } finally {
      setBusy(false);
    }
  }

  const field = (label: string, key: keyof Filters, suffix = "") => (
    <div className="filter-field">
      <label>{label}</label>
      <input value={filters[key]} onChange={(e) => set(key, e.target.value)} placeholder={suffix} />
    </div>
  );

  return (
    <div>
      <h1 className="page-title">Screener</h1>
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-title">Filters (deterministic — SQL/analytics, tanpa AI)</div>
        <div className="filter-grid">
          {field("PER <", "per_max")}
          {field("PBV <", "pbv_max")}
          {field("ROE >", "roe_min", "%")}
          {field("ROA >", "roa_min", "%")}
          {field("DER <", "der_max")}
          {field("Rev Gth >", "revenue_growth_min", "%")}
          {field("NI Gth >", "net_income_growth_min", "%")}
          {field("Div Yield >", "dividend_yield_min", "%")}
          {field("Volume >", "volume_min")}
          {field("Price >", "price_min")}
          {field("Price <", "price_max")}
          {field("RSI >", "rsi_min")}
          {field("RSI <", "rsi_max")}
          <div className="filter-field">
            <label>vs SMA200</label>
            <select value={filters.above_sma200} onChange={(e) => set("above_sma200", e.target.value)}>
              <option value="">Any</option>
              <option value="true">Above</option>
              <option value="false">Below</option>
            </select>
          </div>
        </div>
        <div style={{ marginTop: 12 }}>
          <button className="btn btn-primary" onClick={run} disabled={busy}>{busy ? "Running…" : "Run Screener"}</button>
        </div>
      </div>

      {ran && (
        <div className="card" style={{ overflowX: "auto" }}>
          <div className="card-title">{rows.length} hasil</div>
          {rows.length === 0 ? (
            <div className="empty-state">Tidak ada saham yang cocok dengan filter.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Symbol</th><th className="num">Price</th><th className="num">Chg %</th>
                  <th className="num">Volume</th><th className="num">PER</th><th className="num">PBV</th>
                  <th className="num">ROE</th><th className="num">DER</th><th className="num">NI Gth</th>
                  <th className="num">RSI</th><th className="num">vs SMA200</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.symbol}>
                    <td><Link href={`/stock/${r.symbol}`} className="sym-badge">{r.symbol}</Link></td>
                    <td className="num">{fmtNum(r.price?.close)}</td>
                    <td className={`num ${cls(r.price?.change_pct)}`}>{pct(r.price?.change_pct)}</td>
                    <td className="num">{fmtVol(r.price?.volume)}</td>
                    <td className="num">{r.ratios?.per != null ? fmtNum(r.ratios.per) : "-"}</td>
                    <td className="num">{r.ratios?.pbv != null ? fmtNum(r.ratios.pbv) : "-"}</td>
                    <td className="num">{r.ratios?.roe != null ? fmtNum(r.ratios.roe) + "%" : "-"}</td>
                    <td className="num">{r.ratios?.der != null ? fmtNum(r.ratios.der) : "-"}</td>
                    <td className="num">{r.ratios?.net_income_growth != null ? fmtNum(r.ratios.net_income_growth) + "%" : "-"}</td>
                    <td className="num">{r.technicals?.rsi14 != null ? fmtNum(r.technicals.rsi14) : "-"}</td>
                    <td>{r.technicals?.above_sma200 == null ? "-" : r.technicals.above_sma200 ? "Above" : "Below"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}