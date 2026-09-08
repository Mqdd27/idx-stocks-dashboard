"use client";

import { useEffect, useState } from "react";
import type { Stock, Technicals } from "@/lib/api";
import { api } from "@/lib/api";
import { fmtNum, fmtPrice } from "@/lib/format";

type StatProps = { label: string; value: string; color?: string };

function DecisionStat({ label, value, color }: StatProps) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className={`value ${color || ""}`}>{value}</div>
    </div>
  );
}

export default function PaperDecisionCard({
  symbol,
  stock,
  tech,
}: {
  symbol: string;
  stock: Stock;
  tech: Technicals | null;
}) {
  const [ideas, setIdeas] = useState<any[]>([]);
  const [news, setNews] = useState<any[]>([]);

  useEffect(() => {
    let active = true;
    Promise.all([api.stockTradeIdeas(symbol), api.news(symbol)])
      .then(([tradeIdeas, headlines]) => {
        if (!active) return;
        setIdeas(tradeIdeas.data || []);
        setNews(headlines.data || []);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [symbol]);

  const idea = ideas.find((item) => item.action === "BUY") || ideas[0];
  const trend =
    tech?.above_sma200 == null
      ? "DATA TIDAK CUKUP"
      : tech.above_sma200
        ? "BULLISH · ABOVE SMA200"
        : "BELOW SMA200";
  const risk =
    tech?.rsi14 != null && tech.rsi14 > 70
      ? "RSI OVERBOUGHT"
      : tech?.atr14 &&
          stock.price?.close &&
          tech.atr14 / stock.price.close > 0.06
        ? "ATR TINGGI"
        : "RISIKO TEKNIKAL NORMAL";

  return (
    <div className="terminal-panel" style={{ margin: "16px 0" }}>
      <header className="terminal-panel-head">
        <div>
          <span className="terminal-panel-code">SIM</span>
          <h2>PAPER DECISION CARD</h2>
        </div>
        <span className="data-time">
          PAPER-ONLY · BUKAN REKOMENDASI INVESTASI
        </span>
      </header>
      <div className="stat-strip">
        <DecisionStat
          label="Trend"
          value={trend}
          color={
            tech?.above_sma200
              ? "pos"
              : tech?.above_sma200 === false
                ? "neg"
                : ""
          }
        />
        <DecisionStat
          label="PER"
          value={stock.ratios?.per != null ? fmtNum(stock.ratios.per) : "—"}
        />
        <DecisionStat
          label="PBV"
          value={stock.ratios?.pbv != null ? fmtNum(stock.ratios.pbv) : "—"}
        />
        <DecisionStat
          label="ROE"
          value={
            stock.ratios?.roe != null ? `${fmtNum(stock.ratios.roe)}%` : "—"
          }
        />
        <DecisionStat
          label="Risk"
          value={risk}
          color={risk === "RISIKO TEKNIKAL NORMAL" ? "pos" : "neg"}
        />
      </div>
      {idea ? (
        <div className="stat-strip" style={{ marginTop: 8 }}>
          <DecisionStat
            label="Setup"
            value={`${idea.strategy || "PAPER"} · ${idea.action || "—"}`}
          />
          <DecisionStat
            label="Entry"
            value={`${fmtPrice(idea.entry_low)}–${fmtPrice(idea.entry_high)}`}
          />
          <DecisionStat
            label="Stop Loss"
            value={fmtPrice(idea.stop_loss)}
            color="neg"
          />
          <DecisionStat
            label="TP1 / TP2"
            value={`${fmtPrice(idea.tp1)} / ${fmtPrice(idea.tp2)}`}
            color="pos"
          />
          <DecisionStat
            label="R/R"
            value={idea.risk_reward ? Number(idea.risk_reward).toFixed(2) : "—"}
          />
        </div>
      ) : (
        <div className="terminal-empty">
          NO STORED PAPER SETUP FOR THIS STOCK
        </div>
      )}
      <div className="card" style={{ marginTop: 8 }}>
        <div className="card-title">LATEST NEWS CATALYST</div>
        {news[0] ? (
          <a
            className="ticker-link"
            href={news[0].url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {news[0].title}
          </a>
        ) : (
          <span className="muted">No cached news headline.</span>
        )}
      </div>
    </div>
  );
}
