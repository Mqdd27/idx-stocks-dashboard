"use client";

export function fmtNum(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || isNaN(n)) return "-";
  return n.toLocaleString("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtPrice(n: number | null | undefined): string {
  if (n === null || n === undefined || isNaN(n)) return "-";
  return Math.round(n).toLocaleString("id-ID");
}

export function fmtBig(n: number | null | undefined): string {
  if (n === null || n === undefined || isNaN(n)) return "-";
  const abs = Math.abs(n);
  if (abs >= 1e15) return (n / 1e15).toFixed(2) + " T";
  if (abs >= 1e12) return (n / 1e12).toFixed(2) + " T";
  if (abs >= 1e9) return (n / 1e9).toFixed(2) + " M";
  if (abs >= 1e6) return (n / 1e6).toFixed(2) + " Jt";
  if (abs >= 1e3) return (n / 1e3).toFixed(1) + " Rb";
  return fmtNum(n, 0);
}

export function fmtVol(n: number | null | undefined): string {
  if (n === null || n === undefined || isNaN(n)) return "-";
  return fmtBig(n) + " lembar";
}

export function pct(n: number | null | undefined): string {
  if (n === null || n === undefined || isNaN(n)) return "-";
  return (n > 0 ? "+" : "") + fmtNum(n) + "%";
}

export function cls(n: number | null | undefined): string {
  if (n === null || n === undefined || isNaN(n)) return "";
  return n > 0 ? "pos" : n < 0 ? "neg" : "";
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  const s = Math.floor((Date.now() - t) / 1000);
  if (s < 60) return `${s}d yang lalu`;
  if (s < 3600) return `${Math.floor(s / 60)}m yang lalu`;
  if (s < 86400) return `${Math.floor(s / 3600)}j yang lalu`;
  return `${Math.floor(s / 86400)}h yang lalu`;
}