"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Stock, type Technicals } from "@/lib/api";
import { fmtNum, fmtVol, pct, cls, fmtBig } from "@/lib/format";
import StockChart from "@/components/StockChart";
import AIAssistPanel from "@/components/AIAssistPanel";
import ModelSelector from "@/components/ModelSelector";
import { getModel } from "@/lib/store";

type Tab = "overview" | "chart" | "financials" | "valuation" | "news" | "ai";

export default function StockDetailPage() {
  const { symbol } = useParams() as { symbol: string };
  const [stock, setStock] = useState<Stock | null>(null);
  const [tech, setTech] = useState<Technicals | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [inWatchlist, setInWatchlist] = useState(false);
  const [err, setErr] = useState(false);
  const [flashDir, setFlashDir] = useState<"up" | "down" | null>(null);
  const prevClose = useRef<number | null>(null);

  useEffect(() => {
    let alive = true;
    setStock(null);
    setTech(null);
    setTab("overview");
    prevClose.current = null;
    setFlashDir(null);
    api.stock(symbol).then((s) => alive && setStock(s)).catch(() => alive && setErr(true));
    api.technicals(symbol).then((t) => alive && setTech(t.technicals)).catch(() => {});
    api.watchlist().then((w) => alive && setInWatchlist(w.data.some((x) => x.symbol === symbol))).catch(() => {});
    return () => { alive = false; };
  }, [symbol]);

  useEffect(() => {
    const iv = setInterval(() => {
      api.stock(symbol).then((s) => {
        const c = s.price?.close;
        const p = prevClose.current;
        if (c != null && p != null && c !== p) setFlashDir(c > p ? "up" : "down");
        if (c != null) prevClose.current = c;
        setStock(s);
      }).catch(() => {});
    }, 5000);
    return () => clearInterval(iv);
  }, [symbol]);

  if (err) return <div className="empty-state">Saham tidak ditemukan.</div>;
  if (!stock) return <div className="empty-state"><span className="spin" /> Memuat…</div>;

  const p = stock.price;
  const changePct = p?.change_pct;
  const changeColor = changePct != null ? (changePct >= 0 ? "var(--green)" : "var(--red)") : "var(--text)";

  async function toggleWatchlist() {
    try {
      if (inWatchlist) {
        await api.watchlistRemove(symbol);
      } else {
        await api.watchlistAdd(symbol);
      }
      setInWatchlist(!inWatchlist);
    } catch {
      /* ignore */
    }
  }

  return (
    <div>
      <div className="stock-header">
        <div>
          <h2>{stock.symbol} <span className="name">· {stock.company_name}</span></h2>
          <div className="muted" style={{ marginTop: 2 }}>
            {[stock.sector, stock.subsector].filter(Boolean).join(" / ") || "—"}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          {p ? (
            <>
              <div
              className={`price-big ${flashDir ? `flash-${flashDir}` : ""}`}
              onAnimationEnd={() => setFlashDir(null)}
              style={{ color: changeColor }}
            >
              {p.live && <span className="live-dot" title="Harga realtime (intraday)" />} {fmtNum(p.close)}
            </div>
              <div className={`price-change ${cls(changePct)}`}>
                {p.change != null && `${p.change > 0 ? "+" : ""}${fmtNum(p.change)}`} ({pct(changePct)})
              </div>
            </>
          ) : (
            <div className="muted">Belum ada data harga</div>
          )}
        </div>
      </div>

      <div className="tabs">
        {(["overview", "chart", "financials", "valuation", "news", "ai"] as Tab[]).map((t) => (
          <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
            {t === "ai" ? "AI Analysis" : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab stock={stock} tech={tech} onWatchlist={toggleWatchlist} inWatchlist={inWatchlist} />}
      {tab === "chart" && <StockChart symbol={symbol} />}
      {tab === "financials" && <FinancialsTab symbol={symbol} />}
      {tab === "valuation" && <ValuationTab symbol={symbol} />}
      {tab === "news" && <NewsTab symbol={symbol} />}
      {tab === "ai" && (
        <div className="grid" style={{ gridTemplateColumns: "1fr 400px", gap: 14, alignItems: "start" }}>
          <div>
            <AnalyzeTab symbol={symbol} />
          </div>
          <div>
            <AIAssistPanel symbol={symbol} companyName={stock.company_name} />
          </div>
        </div>
      )}


    </div>
  );
}

function OverviewTab({ stock, tech, onWatchlist, inWatchlist }: { stock: Stock; tech: Technicals | null; onWatchlist: () => void; inWatchlist: boolean }) {
  const p = stock.price;
  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <button className={`btn btn-sm ${inWatchlist ? "" : "btn-primary"}`} onClick={onWatchlist}>
          {inWatchlist ? "★ In Watchlist" : "☆ Add to Watchlist"}
        </button>
      </div>
      <div className="stat-strip">
        <Stat label="Last Price" value={p ? fmtNum(p.close) : "-"} />
        <Stat label="Change" value={p ? pct(p.change_pct) : "-"} color={cls(p?.change_pct)} />
        <Stat label="Open" value={p ? fmtNum(p.open) : "-"} />
        <Stat label="High" value={p ? fmtNum(p.high) : "-"} />
        <Stat label="Low" value={p ? fmtNum(p.low) : "-"} />
        <Stat label="Volume" value={p ? fmtVol(p.volume) : "-"} />
        <Stat label="Prev Close" value={p ? fmtNum(p.previous_close) : "-"} />
        <Stat label="Date" value={p?.date || "-"} />
      </div>
      <h3 className="card-title" style={{ margin: "20px 0 10px" }}>Technicals</h3>
      {tech ? (
        <div className="stat-strip">
          <Stat label="SMA 5" value={tech.sma5 != null ? fmtNum(tech.sma5) : "-"} />
          <Stat label="SMA 20" value={tech.sma20 != null ? fmtNum(tech.sma20) : "-"} />
          <Stat label="SMA 50" value={tech.sma50 != null ? fmtNum(tech.sma50) : "-"} />
          <Stat label="SMA 200" value={tech.sma200 != null ? fmtNum(tech.sma200) : "-"} />
          <Stat label="RSI 14" value={tech.rsi14 != null ? fmtNum(tech.rsi14) : "-"} />
          <Stat label="MACD" value={tech.macd ? fmtNum(tech.macd.macd) : "-"} />
          <Stat label="ATR 14" value={tech.atr14 != null ? fmtNum(tech.atr14) : "-"} />
          <Stat label="52W High" value={tech.high_52w != null ? fmtNum(tech.high_52w) : "-"} />
          <Stat label="52W Low" value={tech.low_52w != null ? fmtNum(tech.low_52w) : "-"} />
          <Stat label="Support" value={tech.support_resistance ? fmtNum(tech.support_resistance.support) : "-"} />
          <Stat label="Resistance" value={tech.support_resistance ? fmtNum(tech.support_resistance.resistance) : "-"} />
          <Stat label="vs SMA200" value={tech.above_sma200 == null ? "-" : tech.above_sma200 ? "Above" : "Below"} />
        </div>
      ) : (
        <div className="empty-state card">Data harga belum cukup untuk kalkulasi teknikal.</div>
      )}
      <h3 className="card-title" style={{ margin: "20px 0 10px" }}>Company</h3>
      <div className="card">
        <table>
          <tbody>
            <Row k="Symbol" v={stock.symbol} />
            <Row k="Company" v={stock.company_name} />
            <Row k="Sector" v={stock.sector || "-"} />
            <Row k="Subsector" v={stock.subsector || "-"} />
            <Row k="Listing Date" v={stock.listing_date || "-"} />
            <Row k="Website" v={stock.website || "-"} />
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value" style={color ? { color: `var(--${color === "pos" ? "green" : "red"})` } : undefined}>{value}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <tr>
      <td className="muted" style={{ width: 160 }}>{k}</td>
      <td>{v}</td>
    </tr>
  );
}

function FinancialsTab({ symbol }: { symbol: string }) {
  const [periodType, setPeriodType] = useState<"annual" | "quarterly">("annual");
  const [rows, setRows] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setLoaded(false);
    api.financials(symbol, periodType).then((r) => { setRows(r.data); setLoaded(true); }).catch(() => setLoaded(true));
  }, [symbol, periodType]);

  return (
    <div>
      <div className="chart-toolbar" style={{ marginBottom: 10 }}>
        <button className={periodType === "annual" ? "active" : ""} onClick={() => setPeriodType("annual")}>Annual</button>
        <button className={periodType === "quarterly" ? "active" : ""} onClick={() => setPeriodType("quarterly")}>Quarterly</button>
      </div>
      {!loaded ? <div className="empty-state"><span className="spin" /> Memuat…</div> : rows.length === 0 ? (
        <div className="empty-state card">
          Data laporan keuangan belum tersedia. Kolektor fundamental berjalan harian; IDX official API diblokir dari server ini (403), data diambil dari Yahoo Finance fundamentals.
        </div>
      ) : (
        <div className="card" style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Period</th>
                <th className="num">Revenue</th>
                <th className="num">Net Income</th>
                <th className="num">Assets</th>
                <th className="num">Liabilities</th>
                <th className="num">Equity</th>
                <th className="num">Op. Cashflow</th>
                <th className="num">Capex</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.period}</td>
                  <td className="num">{r.revenue != null ? fmtBig(r.revenue) : "-"}</td>
                  <td className={`num ${r.net_income != null && r.net_income >= 0 ? "pos" : "neg"}`}>{r.net_income != null ? fmtBig(r.net_income) : "-"}</td>
                  <td className="num">{r.total_assets != null ? fmtBig(r.total_assets) : "-"}</td>
                  <td className="num">{r.total_liabilities != null ? fmtBig(r.total_liabilities) : "-"}</td>
                  <td className="num">{r.total_equity != null ? fmtBig(r.total_equity) : "-"}</td>
                  <td className="num">{r.operating_cashflow != null ? fmtBig(r.operating_cashflow) : "-"}</td>
                  <td className="num">{r.capex != null ? fmtBig(r.capex) : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ValuationTab({ symbol }: { symbol: string }) {
  const [rows, setRows] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.ratios(symbol).then((r) => { setRows(r.data); setLoaded(true); }).catch(() => setLoaded(true));
  }, [symbol]);

  if (!loaded) return <div className="empty-state"><span className="spin" /> Memuat…</div>;
  if (rows.length === 0) return <div className="empty-state card">Rasio valuasi belum tersedia (fundamental belum tersinkron).</div>;

  return (
    <div className="card" style={{ overflowX: "auto" }}>
      <table>
        <thead>
          <tr>
            <th>Period</th><th className="num">EPS</th><th className="num">PER</th><th className="num">PBV</th>
            <th className="num">ROE</th><th className="num">ROA</th><th className="num">DER</th>
            <th className="num">NPM</th><th className="num">Gross Mgn</th><th className="num">Div Yield</th>
            <th className="num">Rev Growth</th><th className="num">NI Growth</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{r.period}</td>
              <td className="num">{r.eps != null ? fmtNum(r.eps) : "-"}</td>
              <td className="num">{r.per != null ? fmtNum(r.per) : "-"}</td>
              <td className="num">{r.pbv != null ? fmtNum(r.pbv) : "-"}</td>
              <td className="num">{r.roe != null ? fmtNum(r.roe) + "%" : "-"}</td>
              <td className="num">{r.roa != null ? fmtNum(r.roa) + "%" : "-"}</td>
              <td className="num">{r.der != null ? fmtNum(r.der) : "-"}</td>
              <td className="num">{r.npm != null ? fmtNum(r.npm) + "%" : "-"}</td>
              <td className="num">{r.gross_margin != null ? fmtNum(r.gross_margin) + "%" : "-"}</td>
              <td className="num">{r.dividend_yield != null ? fmtNum(r.dividend_yield) + "%" : "-"}</td>
              <td className={`num ${cls(r.revenue_growth)}`}>{r.revenue_growth != null ? fmtNum(r.revenue_growth) + "%" : "-"}</td>
              <td className={`num ${cls(r.net_income_growth)}`}>{r.net_income_growth != null ? fmtNum(r.net_income_growth) + "%" : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NewsTab({ symbol }: { symbol: string }) {
  const [rows, setRows] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [model, setModel] = useState(getModel() || "qwen3.5:2b");
  const [summary, setSummary] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sumErr, setSumErr] = useState<string | null>(null);

  useEffect(() => {
    api.news(symbol).then((r) => { setRows(r.data); setLoaded(true); }).catch(() => setLoaded(true));
  }, [symbol]);

  async function summarize() {
    setBusy(true);
    setSumErr(null);
    setSummary(null);
    try {
      const r = await api.aiSummarize(symbol, model);
      setSummary(r.summary);
    } catch (e: any) {
      setSumErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <ModelSelector onChange={(m) => setModel(m)} />
        <button className="btn btn-primary btn-sm" onClick={summarize} disabled={busy || rows.length === 0}>
          {busy ? "Summarizing…" : "Summarize News"}
        </button>
      </div>
      {busy && <div className="queue-note">Local AI is busy. Your request is queued.</div>}
      {summary && (
        <div className="analysis-box" style={{ marginBottom: 14 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Ringkasan Berita</div>
          {summary}
          <div className="analysis-meta">Summarized using: {model}</div>
        </div>
      )}
      {sumErr && <div className="analysis-err">{sumErr}</div>}
      {!loaded ? <div className="empty-state"><span className="spin" /> Memuat…</div> : rows.length === 0 ? (
        <div className="empty-state card">Belum ada berita tersedia untuk {symbol}.</div>
      ) : (
        <div className="card">
          {rows.map((n, i) => (
            <div className="news-item" key={i}>
              <a href={n.url} target="_blank" rel="noopener noreferrer" className="t">{n.title}</a>
              <div className="m">{n.source} · {n.published_at ? new Date(n.published_at).toLocaleString("id-ID") : ""}</div>
              {n.summary && <div className="muted" style={{ marginTop: 3 }}>{n.summary}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AnalyzeTab({ symbol }: { symbol: string }) {
  const [model, setModel] = useState(getModel() || "qwen3.5:2b");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ analysis: string; model: string; provider: string; generated_at: string } | null>(null);
  const [fb, setFb] = useState<{ message: string; provider: string } | null>(null);
  const [queued, setQueued] = useState(0);

  async function analyze(overrideModel?: string) {
    const m = overrideModel || model;
    setBusy(true);
    setFb(null);
    setResult(null);
    setQueued(0);
    let text = "";
    try {
      await api.aiAnalyzeStream(
        symbol,
        m,
        (d) => {
          text += d;
          setResult({ analysis: text, model: m, provider: "streaming", generated_at: new Date().toISOString() });
        },
        (meta) => setResult({ analysis: text, model: meta.model, provider: meta.provider, generated_at: meta.generated_at }),
        (msg, provider) => setFb({ message: msg, provider: provider || "unknown" }),
      );
    } catch (e: any) {
      setFb({ message: String(e.message || e), provider: "unknown" });
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!busy) return;
    const iv = setInterval(() => {
      api.aiQueue().then((q) => setQueued(q.queued || 0)).catch(() => {});
    }, 5000);
    return () => clearInterval(iv);
  }, [busy]);

  return (
    <div>
      <div className="card">
        <div className="card-title">AI Analysis</div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <ModelSelector onChange={(m) => setModel(m)} />
          <button className="btn btn-primary" onClick={() => analyze()} disabled={busy}>
            {busy ? "Analyzing…" : "Analyze with AI"}
          </button>
        </div>
        <div className="muted" style={{ marginTop: 10, fontSize: 11 }}>
          Analisis dijalankan hanya saat tombol ditekan. Data snapshot: harga, teknikal, fundamental, aksi korporasi & berita terbaru.
        </div>
      </div>

      {busy && (
        <div className="queue-note" style={{ marginTop: 12 }}>
          {queued > 0
            ? `Model lokal sedang sibuk — ${queued} request dalam antrian.`
            : "Memproses analisis… (model lokal butuh ±2–3 menit, cloud ±10–30 detik)"}
        </div>
      )}

      {fb && (
        <div className="analysis-err">
          <div>{fb.message}</div>
          <div style={{ fontSize: 12, color: "var(--muted)", margin: "8px 0" }}>Fallback available: cloud model</div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-sm" onClick={() => analyze(model)} disabled={busy}>Retry Local</button>
            <button className="btn btn-sm btn-primary" onClick={() => api.cloudFallbackModel().then((m) => analyze(m))} disabled={busy}>Use Cloud</button>
          </div>
        </div>
      )}

      {result && (
        <div className="analysis-box" style={{ marginTop: 14 }}>
          <MarkdownOutput text={result.analysis} />
          <div className="analysis-meta">
            Analyzed using: <strong>{result.model}</strong> ({result.provider === "ollama" ? "LOCAL" : "CLOUD via 9Router"})
            <br />
            Generated at: {new Date(result.generated_at).toLocaleString("id-ID")}
          </div>
        </div>
      )}    </div>
  );
}

function MarkdownOutput({ text }: { text: string }) {
  return <div className="markdown-output">{text.split("\n").map((line, index) => {
    const value = line.trim();
    if (!value) return <div className="markdown-gap" key={index} />;
    if (/^---+$/.test(value)) return <hr key={index} />;
    if (/^#{1,6}\s/.test(value)) return <h3 key={index}>{inlineMarkdown(value.replace(/^#{1,6}\s/, ""))}</h3>;
    if (/^[-*]\s/.test(value)) return <div className="markdown-item" key={index}>• {inlineMarkdown(value.slice(2))}</div>;
    return <p key={index}>{inlineMarkdown(value)}</p>;
  })}</div>;
}
function inlineMarkdown(value: string) {
  return value.split(/(\*\*[^*]+\*\*)/g).map((part, index) => part.startsWith("**") && part.endsWith("**") ? <strong key={index}>{part.slice(2, -2)}</strong> : part);
}
