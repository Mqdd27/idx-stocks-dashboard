# Stocks Dashboard IDX — Installation & Operations Guide

Detailed installation, configuration, operational routines, and API documentation for Stocks Dashboard IDX.

---

## 📋 System Requirements

- **OS**: Ubuntu 22.04 / 24.04 LTS (native deployment, non-containerized)
- **Python**: 3.12+
- **Node.js**: 22+ (npm 10+)
- **Database**: PostgreSQL 16+
- **AI Gateway** *(optional)*: 9Router (`:20128`) / Ollama (`:11434`)

---

## 🛠️ Step-by-Step Installation

### 1. Database Setup

```bash
sudo -u postgres psql -c "CREATE USER stocks_app WITH PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "CREATE DATABASE stocks OWNER stocks_app;"
psql -U stocks_app -d stocks -f /opt/stocks-dashboard/scripts/schema.sql
```

### 2. Backend Installation

```bash
cd /opt/stocks-dashboard/backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 3. Environment Configuration

Create `/etc/stocks-dashboard/backend.env`:

```env
DATABASE_URL=postgresql+psycopg2://stocks_app:your_secure_password@127.0.0.1:5432/stocks
NINE_ROUTER_URL=http://127.0.0.1:20128/v1
NINE_ROUTER_API_KEY=sk-...
OLLAMA_URL=http://127.0.0.1:11434
DEFAULT_AI_MODEL=qwen3.5:2b
ADMIN_API_TOKEN=your_admin_secret_token
TZ=Asia/Jakarta
AI_TRADING_ENABLED=true
```

### 4. Frontend Build

```bash
cd /opt/stocks-dashboard/frontend
npm install
npm run build
```

### 5. Systemd Services Setup

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now stocks-backend stocks-frontend stocks-collector stocks-daily.timer stocks-recommendation.timer ai-trading-batch.timer market-calendar-sync.timer
```

---

## ⚙️ Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://...` | PostgreSQL connection string |
| `ADMIN_API_TOKEN` | — | Secret token for protected API mutations |
| `TZ` | `Asia/Jakarta` | Market timezone boundary |
| `AI_TRADING_ENABLED` | `false` | Master toggle for TradingAgents AI analysis |
| `TRADINGAGENTS_QUICK_THINK_LLM` | `cx/gpt-5.4-mini` | Fast model for initial screening |
| `TRADINGAGENTS_DEEP_THINK_LLM` | `cx/gpt-5.6-sol` | Deep model for full report generation |
| `ENABLE_FRED_ENRICHMENT` | `false` | Macro enrichment toggle |
| `ENABLE_POLYMARKET_ENRICHMENT` | `false` | Prediction market enrichment toggle |
| `CORS_ALLOWED_ORIGINS` | `https://stocks.mqdd.my.id,...` | Allowed web origins |

---

## ⏰ Systemd Services & Timers

| Unit | Schedule / Type | Description |
|---|---|---|
| `stocks-backend.service` | Always active | FastAPI REST & SSE API on `:8200` |
| `stocks-frontend.service` | Always active | Next.js production server on `:3101` |
| `stocks-collector.service` | Always active | Intraday price polling (every 30s during market hours) |
| `stocks-daily.timer` | Mon-Fri **16:30 & 05:30 WIB** | Daily price, financial statement, and news sync |
| `stocks-recommendation.timer` | Mon-Fri market sessions | Paper and TradingAgents strategy generation |
| `ai-trading-batch.timer` | Every 5 minutes | Atomic DB-claimed AI batch execution |
| `market-calendar-sync.timer` | Daily **03:00 WIB** | Sync IDX holidays and calendar status |

---

## 🌐 API Endpoints Summary

### Market & Stock Data
- `GET /api/market/overview`: IHSG composite, top gainers, top losers, most active.
- `GET /api/market/status`: Current IDX session, trading status, next market open.
- `GET /api/market/calendar/status`: Calendar sync freshness, source, upcoming holidays.
- `GET /api/stocks/{symbol}`: Company profile, ratios, latest price.
- `GET /api/stocks/{symbol}/prices?range=1y`: Historical daily prices (`1m/3m/6m/1y/5y`).
- `GET /api/stocks/{symbol}/financials`: Annual and quarterly financial statements.
- `GET /api/stocks/{symbol}/ratios`: Financial ratios history.
- `GET /api/stocks/{symbol}/technicals`: Technical indicators (RSI, MACD, SMA, EMA, ATR, Bollinger).

### Strategy & Performance
- `GET /api/recommendations/strategy-performance/{strategy}`: Strategy performance aggregates (`BSJP` / `BPJS`, `daily`/`weekly`/`monthly`/`yearly`).
- `GET /api/recommendations/strategy-performance/{strategy}/trades`: Strategy trade drilldown with normalized equity index.
- `GET /api/recommendations/today`: Today's actionable quant and TradingAgents picks.
- `GET /api/operations/health`: System health (calendar, collector, batch queue, Telegram failures).

---

## 🛠️ CLI Operations

```bash
cd /opt/stocks-dashboard

# Check IDX Market Status
PYTHONPATH=backend:. ./backend/venv/bin/python -m app.cli market-status

# Add Manual Holiday Override
PYTHONPATH=backend:. ./backend/venv/bin/python -m app.cli market-holiday add   --date 2027-08-17   --name "Hari Kemerdekaan RI"   --type PUBLIC_HOLIDAY

# Force Calendar Sync
PYTHONPATH=backend:. ./backend/venv/bin/python -m app.sync_calendar

# Run Backend Test Suite
cd backend && ./venv/bin/python -m unittest discover -s tests -v
```
