# Stocks Dashboard IDX

Dashboard saham Indonesia (IDX) self-hosted lengkap dengan data historis, laporan keuangan, rasio, berita, screener, dan asisten AI — menampilkan **842 emiten** yang terdaftar di Bursa Efek Indonesia.

## Fitur

- **Harga harian 5 tahun** per emiten (grafik candlestick `lightweight-charts`)
- **Laporan keuangan** tahunan & kuartalan (13 jenis pos) + rasio otomatis (PER, PBV, ROE, margin, dll.)
- **Berita** per emiten (Google News RSS) & berita pasar terbaru
- **Screener** fundamental + **market overview** (gainers/losers)
- **Asisten AI** — analisis saham, chat streaming, dan ringkasan berita:
  - Model **lokal** via Ollama (`qwen3.5:2b`, `think:false`, streaming)
  - Model **cloud** via 9Router (`cx/*`), dengan fallback otomatis
  - Model yang butuh akun eksternal otomatis ditandai & di-skip
- **Watchlist** per pengguna
- Tidak ada eksekusi trading otomatis (read-only data)

## Arsitektur

```
┌────────────┐   ┌─────────────────┐   ┌──────────────┐
│  Browser   │──▶│  Nginx :80/443  │──▶│  Frontend    │
│            │   │  (SSL/Cloudflare)│   │  Next.js     │
└────────────┘   └─────────────────┘   │  :3100       │
                                       └──────┬───────┘
                              ┌────────────────┴────────┐
                              │  Backend  FastAPI :8200 │
                              └───────┬────────┬────────┘
                    ┌─────────────────┴─┐   ┌──┴──────────────┐
                    │  PostgreSQL :5432 │   │  AI:            │
                    │  (database stocks)│   │  Ollama :11434  │
                    └───────────────────┘   │  9Router :20128│
                                            └─────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Collector (systemd): Yahoo Finance + Google News RSS        │
│  - daily: harga, fundamentals, berita  (daily_sync.py)       │
│  - intraday: harga 30 detik saat market buka (intraday.py)   │
└─────────────────────────────────────────────────────────────┘
```

## Struktur Direktori

```
/opt/stocks-dashboard/
├── backend/               # FastAPI
│   ├── app/
│   │   ├── main.py        # 25+ endpoint REST + SSE streaming AI
│   │   ├── ai_provider.py # Ollama + 9Router, queue, fallback, model discovery
│   │   ├── analytics.py   # technicals, screener, market overview
│   │   ├── models.py      # SQLAlchemy models
│   │   ├── config.py      # settings dari env
│   │   └── security.py    # rate limiting, CORS
│   └── venv/
├── collector/             # Data pipeline (berjalan di systemd)
│   ├── daily_sync.py      # sync harga + fundamentals + berita
│   ├── intraday.py        # poll harga intraday saat market buka
│   ├── yahoo.py           # Yahoo Finance client (chart, fundamentals, 429 backoff)
│   ├── news.py            # Google News RSS collector
│   └── seed_companies.json# 842 emiten IDX (symbol, sektor, yahoo_symbol)
├── frontend/              # Next.js 15 + React 19 + TypeScript
│   ├── app/               # halaman: home, stock, watchlist, screener, news, ai, settings
│   ├── components/        # StockChart, AIAssistPanel, ModelSelector, Shell
│   └── lib/               # api.ts, store (localStorage), format
├── shared/                # common.py, fundamentals_state.json (runtime)
├── scripts/schema.sql     # skema PostgreSQL
└── logs/                  # log layanan
```

## Instalasi

Prerequisite: Python 3.12+, Node 22+, PostgreSQL 16+, dan akun 9Router/Ollama (opsional untuk AI).

```bash
# 1. Database
sudo -u postgres psql -c "CREATE USER stocks_app WITH PASSWORD '...'"
sudo -u postgres psql -c "CREATE DATABASE stocks OWNER stocks_app"
psql -U stocks_app -d stocks -f /opt/stocks-dashboard/scripts/schema.sql

# 2. Backend
cd /opt/stocks-dashboard/backend
python3 -m venv venv && venv/bin/pip install -r requirements.txt  # fastapi, uvicorn, sqlalchemy, httpx, psycopg2-binary, python-dotenv

# 3. Konfigurasi — buat /etc/stocks-dashboard/backend.env
DATABASE_URL=postgresql+psycopg2://stocks_app:PASS@127.0.0.1:5432/stocks
NINE_ROUTER_URL=http://127.0.0.1:20128/v1
NINE_ROUTER_API_KEY=sk-...
OLLAMA_URL=http://127.0.0.1:11434
DEFAULT_AI_MODEL=qwen3.5:2b
TZ=Asia/Jakarta

# 4. Frontend
cd /opt/stocks-dashboard/frontend && npm install && npm run build

# 5. Systemd
sudo systemctl daemon-reload
sudo systemctl enable --now stocks-backend stocks-frontend stocks-collector stocks-daily.timer
```

## Variabel Env (backend)

| Variabel | Default | Keterangan |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://stocks_app:stocks_app@127.0.0.1:5432/stocks` | Koneksi PostgreSQL |
| `NINE_ROUTER_URL` | `http://127.0.0.1:20128/v1` | Gateway AI cloud |
| `NINE_ROUTER_API_KEY` | — | API key 9Router |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama lokal |
| `DEFAULT_AI_MODEL` | `qwen3.5:2b` | Model default |
| `ALLOW_AI_FALLBACK` | `false` | Fallback cloud saat model lokal gagal |
| `AI_RATE_LIMIT_PER_MINUTE` | `20` | Rate limit AI |
| `MAX_CHAT_LENGTH` | `4000` | Panjang chat maksimal |
| `MAX_CONTEXT_SYMBOLS` | `8` | Konteks fundamental max per analisis |
| `MARKET_POLL_INTERVAL` | `30` | Interval intraday (detik) |
| `TZ` | `Asia/Jakarta` | Zona waktu |

## Jadwal Sync (systemd)

| Service/Timer | Jadwal | Aksi |
|---|---|---|
| `stocks-daily.timer` | Sen–Jum **16:30 & 05:30 WIB** | Sync harga + fundamentals + berita semua emiten |
| `stocks-daily.service` | di-trigger timer | `daily_sync.py` (bootstrap penuh ±2 jam, harian ±5–10 menit) |
| `stocks-collector.service` | selalu aktif | Poll harga intraday tiap 30 detik saat market buka (09:00–16:00 WIB) |
| `stocks-backend.service` | selalu aktif | API :8200 |
| `stocks-frontend.service` | selalu aktif | Web :3100 |

## API (seleksi)

| Endpoint | Keterangan |
|---|---|
| `GET /api/stocks` | Daftar emiten (search/paginate) |
| `GET /api/stocks/{symbol}` | Profil + harga terbaru |
| `GET /api/stocks/{symbol}/prices?range=1y` | Harga harian (`1m/3m/6m/1y/5y`) |
| `GET /api/stocks/{symbol}/financials` | Laporan keuangan tahunan/kuartalan |
| `GET /api/stocks/{symbol}/ratios` | Rasio keuangan |
| `GET /api/stocks/{symbol}/technicals` | RSI, MACD, SMA, Bollinger, EMA |
| `GET /api/stocks/{symbol}/news` | Berita emiten |
| `GET /api/market/overview` | Ringkasan pasar (IHSG, top movers) |
| `GET /api/market/gainers` / `losers` | Pergerakan terbesar |
| `GET /api/screener` | Screener fundamental |
| `GET /api/ai/models` | Daftar model AI (auto-discover Ollama + 9Router, TTL 30 detik) |
| `GET /api/ai/queue-status` | Antrian AI |
| `POST /api/ai/analyze` | Analisis AI (streaming SSE) |
| `POST /api/ai/chat` | Chat streaming (SSE) |
| `POST /api/ai/summarize` | Ringkasan berita |
| `GET/POST /api/watchlist` | Watchlist |

## Catatan Deployment

- Nginx: frontend `:3100`, 9Router `:20128`
- Data harga dari **Yahoo Finance** (IDX resmi memblokir scraping); 429 di-backoff otomatis
- Ticker IDX = `KODE.JK` (contoh `BBCA.JK`), indeks = `^JKSE`
- Build frontend harus sebagai user pemilik (bukan `stocks`) lalu `chown -R stocks:stocks` sebelum restart service


## IDX Market Calendar

Dashboard menggunakan `Asia/Jakarta` dan calendar service sebagai single source of truth untuk status IDX:

- `OPEN`, `CLOSED`, `PRE_OPEN`, `BREAK`, `POST_MARKET`
- `WEEKEND`, `PUBLIC_HOLIDAY`, `EXCHANGE_HOLIDAY`
- Collector intraday tidak melakukan polling saat tidak ada sesi perdagangan.
- Price sync harian melewati hari non-trading; job background tetap dapat berjalan.
- Harga API menyediakan `is_live`, `is_stale`, `last_updated`, dan `market_status`.

### Calendar Data Priority

1. Kalender atau pengumuman resmi IDX
2. Manual override IDX
3. Baseline hari libur nasional Indonesia
4. Weekend rule

File baseline/import manual:

```text
shared/market_calendar.json
```

Format:

```json
[
  {
    "date": "2027-08-17",
    "name": "Hari Kemerdekaan Republik Indonesia",
    "holiday_type": "PUBLIC_HOLIDAY",
    "source": "Indonesia public holiday baseline",
    "source_url": "https://example.invalid/source"
  }
]
```

Jangan gunakan URL contoh di atas sebagai source aktual. Isi `source_url` hanya jika tersedia sumber resmi.

### API Calendar

| Endpoint | Keterangan |
|---|---|
| `GET /api/market/status` | Status IDX saat ini, sesi dan next open |
| `GET /api/market/calendar?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | Trading/non-trading days |
| `GET /api/market/holidays` | Holiday database |
| `GET /api/market/events?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | IPO/corporate actions yang tersedia di database |

UI tersedia pada route:

```text
/calendar
```

### CLI Management

```bash
cd /opt/stocks-dashboard
PYTHONPATH=backend:. backend/venv/bin/python -m app.cli market-status
PYTHONPATH=backend:. backend/venv/bin/python -m app.cli market-calendar --month 2027-08
PYTHONPATH=backend:. backend/venv/bin/python -m app.cli market-holiday add \
  --date 2027-08-17 \
  --name "Hari Kemerdekaan Republik Indonesia" \
  --type PUBLIC_HOLIDAY
PYTHONPATH=backend:. backend/venv/bin/python -m app.cli market-holiday remove --date 2027-08-17
PYTHONPATH=backend:. backend/venv/bin/python -m app.cli market-override \
  --date 2027-08-18 \
  --trading-day \
  --reason "IDX special trading session"
PYTHONPATH=backend:. backend/venv/bin/python -m app.sync_calendar
```

### Calendar Scheduler

`market-calendar-sync.timer` menjalankan sync setiap hari pukul **03:00 WIB** dari `shared/market_calendar.json`.

```bash
sudo systemctl enable --now market-calendar-sync.timer
sudo systemctl list-timers market-calendar-sync.timer
sudo systemctl start market-calendar-sync.service
```

Tanggal bergerak seperti Idulfitri, Nyepi, Waisak, Imlek, dan cuti bersama harus diperbarui dari sumber resmi pemerintah/IDX atau file JSON manual.
