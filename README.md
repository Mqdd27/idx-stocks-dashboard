# Stocks Dashboard IDX

Dashboard saham Indonesia untuk memantau pasar IDX, melakukan riset emiten, dan menjalankan simulasi strategi paper trading. Tersedia sebagai workstation web mandiri dan aplikasi desktop lokal untuk macOS, Windows, serta Linux.

Mencakup lebih dari **840 emiten IDX** dan IHSG. Bukan platform broker: seluruh keputusan dan posisi trading tetap berupa simulasi.

## Fitur

### Riset pasar

- **Terminal pasar**: IHSG, top gainers, top losers, saham paling aktif, status sesi IDX, dan watchlist.
- **Detail emiten**: harga historis hingga lima tahun, chart candlestick, volume, SMA, EMA, RSI, MACD, Bollinger Bands, ATR, laporan keuangan, dan rasio valuasi.
- **Market Feed & Stock News**: berita pasar dan berita per emiten dari Google News RSS, dengan filter sumber, sentimen, dan tanggal.
- **Foreign Flow**: data EOD resmi IDX dari `ForeignBuy` dan `ForeignSell`; disajikan sebagai volume saham, bukan nilai Rupiah.
- **Broker Activity**: turnover EOD broker tingkat pasar dari IDX. Data ini tidak diklaim sebagai aliran beli/jual per saham atau foreign flow.
- **Penyaring fundamental**: filter valuasi, pertumbuhan, profitabilitas, dan setup teknikal.

### Paper trading dan performa

- **Mesin paper trading kuantitatif**: setup teknikal deterministik, position sizing, target, stop loss, dan pencatatan hasil.
- **Riset AI TradingAgents**: analisis multi-agent dengan validasi harga dan target deterministik sebelum dapat dipakai sebagai rekomendasi simulasi.
- **BSJP & BPJS**: analitik beli sore-jual pagi dan beli pagi-jual sore, termasuk win rate, profit factor, return, equity index, dan rincian transaksi.
- **AI Watchlist & AI Auto Trade**: alur kerja riset dan simulasi paper trading; tidak ada integrasi broker atau order riil.

### Operasional

- **Operations Health**: status kalender IDX, freshness kolektor, batch AI, dan kegagalan pengiriman notifikasi.
- **Pengiriman Telegram tahan duplikasi**: Hermes mengirim daily brief dan laporan performa dengan idempotensi logical-key/content-hash.
- **Kalender pasar Jakarta**: sesi pasar, hari libur, dan keputusan tanggal bisnis menggunakan `Asia/Jakarta`.

## Aplikasi desktop

Aplikasi desktop menjalankan dashboard, API, dan SQLite lokal di perangkat.

- Tersedia bundle Tauri untuk **macOS, Windows, dan Linux** melalui artefak GitHub Actions.
- Setup awal hanya meminta **password master lokal**. Password disimpan sebagai hash Argon2; konfigurasi sensitif menggunakan OS keyring.
- Database SQLite dan daftar emiten dibuat lokal saat pertama dijalankan.
- Harga awal IHSG dan saham likuid diambil di latar belakang. Dashboard menunjukkan progres ticker, jumlah berhasil, dan persentase selama proses ini berjalan.
- **9Router/AI opsional**: masukkan URL, API key, dan model dari `Pengaturan → AI / 9Router` hanya jika ingin memakai fitur AI. Simpan konfigurasi lalu gunakan `RESTART DESKTOP APP` untuk menerapkannya.
- Semua endpoint desktop hanya bind ke `127.0.0.1`.

Build desktop saat ini adalah artefak pengujian. Pengujian langsung baru dilakukan di macOS; paket Windows dan Linux saat ini hanya tervalidasi melalui build CI. Artefak macOS belum ditandatangani dan dinotarize Apple; Gatekeeper mungkin memerlukan penghapusan quarantine secara manual sebelum aplikasi dapat dibuka.

## Arsitektur

```text
Yahoo Finance + Google News RSS + IDX EOD sources
  -> PostgreSQL (web) / SQLite (desktop)
  -> FastAPI API, analytics, paper trading engine, recommendation services
  -> Next.js workstation UI / Tauri desktop shell

AI opsional:
9Router atau Ollama
  -> Riset TradingAgents dan alur kerja berbantuan AI
```

## Quick links

- [Installation & Operations](./INSTALLATION.md)
- [Architecture](./INSTALLATION.md#architecture)
- [Environment Variables](./INSTALLATION.md#environment-variables)
- [Systemd Services & Timers](./INSTALLATION.md#systemd-services--timers)
- [API Endpoints](./INSTALLATION.md#api-endpoints-summary)

## Security & data notes

- Proyek ini **tidak** menempatkan order riil atau terhubung ke broker.
- Output AI adalah bantuan riset, bukan nasihat investasi atau jaminan imbal hasil.
- Foreign Flow memakai field resmi IDX untuk volume saham beli/jual asing. Broker Activity dan Foreign Flow memiliki semantik sumber yang berbeda dan tidak boleh saling dilabeli.
- Kolektor produksi, scheduler, Telegram, dan eksekusi AI memiliki kontrol operasional terpisah. Pertahankan `AI_TRADING_ENABLED=false` kecuali telah sengaja dikonfigurasi dan diuji.
