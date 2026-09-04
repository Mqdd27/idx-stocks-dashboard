# Stocks Dashboard IDX

Indonesian stock market dashboard self-hosted with historical price analytics, financial statements, ratios, news, fundamental screening, watchlists, paper trading, TradingAgents AI research, BSJP/BPJS strategy performance, and Telegram brief delivery.

Supports **840+ companies** listed on the Indonesia Stock Exchange (IDX).

---

## 📌 Quick Links

- [Installation & Deployment Guide](./INSTALLATION.md)
- [Architecture & Data Pipeline](./INSTALLATION.md#architecture)
- [Environment Configuration](./INSTALLATION.md#environment-variables)
- [Systemd Services & Timers](./INSTALLATION.md#systemd-services--timers)
- [API Reference](./INSTALLATION.md#api-endpoints-summary)

---

## ✨ Features

- **Interactive Market Terminal**: Dense dark workstation interface inspired by financial terminals, displaying market overview, IHSG composite index, top gainers, top losers, and most active movers.
- **5-Year Price Analytics**: Candlestick charts powered by `lightweight-charts` with SMA, EMA, RSI, MACD, Bollinger Bands, ATR, and volume analysis.
- **Financial Statements & Ratios**: Annual and quarterly financial statements (13 position items) with auto-calculated valuation and performance ratios (PER, PBV, ROE, ROA, DER, NPM, margins).
- **Google News Integration**: Ticker-specific and general market news from Google News RSS feeds with automated backoff.
- **Fundamental Screener**: Filter stocks across valuation, growth, profitability, and technical setup parameters.
- **Dual Paper Trading Engine**:
  - **Quant Engine**: Deterministic technical setup generation with automated position sizing, risk management, and outcome tracking.
  - **TradingAgents AI**: Multi-agent LLM analysis via local 9Router (`cx/*` models) with strict price/target validation.
- **BSJP & BPJS Strategy Analytics**:
  - **BSJP (Beli Sore Jual Pagi)**: Overnight momentum strategy analytics.
  - **BPJS (Beli Pagi Jual Sore)**: Intraday setup analytics with automatic overnight anomaly detection.
  - **Performance Dashboard**: Win rate, net return, profit factor, best/worst trade, and normalized equity index curves at `/performance`.
- **Durable Telegram Delivery**: Automated daily market briefs, performance reports, and image charts delivered via Hermes scheduler with content-hash and logical-key idempotency.
- **Operations Health Monitoring**: Real-time tracking of calendar sync freshness, collector lag, batch queue progress, and Telegram delivery status at `/operations`.

---

## 🏗️ Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    Browser Workstation UI                   │
│         Next.js 15 · React 19 · TypeScript · Bloomberg Dark │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / SSE
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend (:8200)                  │
│       Jakarta TZ · Quant Setup · Performance Service        │
└──────────────┬───────────────┬───────────────┬──────────────┘
               │               │               │
  ┌────────────▼─────────┐ ┌───▼───────────┐ ┌─▼──────────────┐
  │ PostgreSQL Database  │ │ Ollama Local  │ │ 9Router Gateway│
  │ (market/paper/outcomes)│ │ (:11434)      │ │ (:20128)       │
  └──────────────────────┘ └───────────────┘ └────────────────┘
```

See [INSTALLATION.md](./INSTALLATION.md) for step-by-step setup instructions.
