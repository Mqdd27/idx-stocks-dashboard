"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  
} from "lightweight-charts";
import { api } from "@/lib/api";

const RANGES = ["1D", "1W", "1M", "3M", "6M", "1Y", "3Y", "5Y"] as const;
const INDICATORS = ["SMA20", "SMA50", "SMA200", "EMA", "RSI", "MACD", "BOLL"] as const;

interface Props {
  symbol: string;
  initial?: string;
}

export default function StockChart({ symbol, initial = "1Y" }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const overlayRef = useRef<ISeriesApi<"Line">[]>([]);
  const [range, setRange] = useState(initial);
  const [activeInd, setActiveInd] = useState<string[]>([]);
  const [legend, setLegend] = useState<string[]>([]);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0d121d" },
        textColor: "#7d879c",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1b2436" },
        horzLines: { color: "#1b2436" },
      },
      width: containerRef.current.clientWidth,
      height: 380,
      timeScale: { borderColor: "#273149", rightOffset: 6 },
      rightPriceScale: { borderColor: "#273149" },
      crosshair: { mode: 0 },
    });
    chartRef.current = chart;
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#00c176",
      downColor: "#ff4d5e",
      borderUpColor: "#00c176",
      borderDownColor: "#ff4d5e",
      wickUpColor: "#00c176",
      wickDownColor: "#ff4d5e",
    });
    const vol = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      color: "#273149",
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    candleRef.current = candles;
    volRef.current = vol;
    const onResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volRef.current = null;
      overlayRef.current = [];
    };
  }, [symbol]);

  useEffect(() => {
    let alive = true;
    api.prices(symbol, range).then((res) => {
      if (!alive || !chartRef.current || !candleRef.current) return;
      const candles = res.data
        .filter((d) => d.open != null && d.close != null)
        .map((d) => ({
          time: d.time,
          open: d.open,
          high: d.high ?? d.close,
          low: d.low ?? d.close,
          close: d.close,
        }));
      const vols = res.data
        .filter((d) => d.volume != null)
        .map((d) => ({
          time: d.time,
          value: d.volume,
          color: d.close >= (d.open ?? d.close) ? "rgba(0,193,118,.45)" : "rgba(255,77,94,.45)",
        }));
      candleRef.current.setData(candles);
      volRef.current?.setData(vols);
      chartRef.current?.timeScale().fitContent();
      if (res.data.length > 0) {
        const last = res.data[res.data.length - 1];
        const prev = res.data[res.data.length - 2];
        const chg = prev ? last.close - prev.close : 0;
        const pct = prev ? (chg / prev.close) * 100 : 0;
        setLegend([`${symbol} ${last.close.toLocaleString("id-ID")}`, `${chg > 0 ? "+" : ""}${chg.toFixed(2)} (${pct > 0 ? "+" : ""}${pct.toFixed(2)}%)`]);
      }
    }).catch(() => {});
    return () => { alive = false; };
  }, [symbol, range]);

  function toggleIndicator(ind: string) {
    setActiveInd((prev) => {
      const has = prev.includes(ind);
      const next = has ? prev.filter((x) => x !== ind) : [...prev, ind];
      applyIndicators(next);
      return next;
    });
  }

  function openTradingView() {
    const base = symbol.replace(/\.JK$/, "");
    window.open(`https://www.tradingview.com/chart/?symbol=IDX:${base}`, "_blank", "noopener");
  }

  function applyIndicators(inds: string[]) {
    if (!chartRef.current || !candleRef.current) return;
    overlayRef.current.forEach((s) => chartRef.current?.removeSeries(s));
    overlayRef.current = [];
    api.technicals(symbol).then((res) => {
      const t = res.technicals;
      if (!t || !chartRef.current) return;
      const series: ISeriesApi<"Line">[] = [];
      const addLine = (data: { time: string; value: number }[], color: string, title: string) => {
        if (data.length === 0) return;
        const s = chartRef.current!.addSeries(LineSeries, {
          color,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          title,
        });
        s.setData(data.map((d) => ({ time: d.time, value: d.value })));
        series.push(s);
      };
      // SMA/EMA overlays need full series; fetch prices to build them client-side is
      // heavier, so we fetch technicals values only for the current point. For
      // proper overlays we recompute from price history:
      if (inds.some((i) => ["SMA20", "SMA50", "SMA200", "EMA"].includes(i))) {
        api.prices(symbol, range).then((pres) => {
          if (!aliveRef.current || !chartRef.current) return;
          const closes = pres.data.map((d) => ({ time: d.time, close: d.close }));
          if (inds.includes("SMA20")) addLine(sma(closes, 20), "#f6a623", "SMA20");
          if (inds.includes("SMA50")) addLine(sma(closes, 50), "#3e9cff", "SMA50");
          if (inds.includes("SMA200")) addLine(sma(closes, 200), "#27c2d1", "SMA200");
          if (inds.includes("EMA")) addLine(ema(closes, 20), "#e8ecf4", "EMA20");
          overlayRef.current.push(...series);
        });
      } else if (inds.includes("BOLL")) {
        // single-point markers via horizontal lines not supported; skip overlay
      }
      if (inds.includes("RSI") || inds.includes("MACD")) {
        // RSI/MACD shown in legend summary
        const parts: string[] = [];
        if (inds.includes("RSI") && t.rsi14 != null) parts.push(`RSI14 ${t.rsi14}`);
        if (inds.includes("MACD") && t.macd) parts.push(`MACD ${t.macd.macd} / SIG ${t.macd.signal}`);
        setLegend((prev) => [...prev.slice(0, 2), ...parts]);
      }
      if (inds.includes("BOLL") && t.bollinger) {
        const bb = t.bollinger;
        setLegend((prev) => [...prev.slice(0, 2), `BB ${bb.upper}/${bb.middle}/${bb.lower}`]);
      }
    });
  }

  const aliveRef = useRef(true);

  function sma(data: { time: string; close: number }[], n: number) {
    const out: { time: string; value: number }[] = [];
    for (let i = n - 1; i < data.length; i++) {
      let s = 0;
      for (let j = 0; j < n; j++) s += data[i - j].close;
      out.push({ time: data[i].time, value: s / n });
    }
    return out;
  }

  function ema(data: { time: string; close: number }[], n: number) {
    const k = 2 / (n + 1);
    let prev = data[0].close;
    const out: { time: string; value: number }[] = [];
    for (let i = 1; i < data.length; i++) {
      prev = data[i].close * k + prev * (1 - k);
      if (i >= n) out.push({ time: data[i].time, value: prev });
    }
    return out;
  }

  return (
    <div className="chart-wrap">
      <div className="chart-toolbar">
        {RANGES.map((r) => (
          <button key={r} className={range === r ? "active" : ""} onClick={() => setRange(r)}>{r}</button>
        ))}
        <span style={{ flex: 1 }} />
        {INDICATORS.map((i) => (
          <button key={i} className={activeInd.includes(i) ? "active" : ""} onClick={() => toggleIndicator(i)}>
            {i}
          </button>
        ))}
      </div>
      <div className="legend">{legend.map((l, i) => <span key={i}>{l}</span>)}</div>
      <div className="tv-overlay">
        <div className="tv-badge" onClick={openTradingView} title="Buka di TradingView">TradingView ↗</div>
        <div ref={containerRef} onClick={openTradingView} />
      </div>
    </div>
  );
}