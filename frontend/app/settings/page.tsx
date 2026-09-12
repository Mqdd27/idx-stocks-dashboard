"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getFallback, getModel, setFallback } from "@/lib/store";
import DesktopPairing from "@/components/DesktopPairing";

function stamp(value?: string) {
  return value
    ? new Date(value).toLocaleString("id-ID", { timeZone: "Asia/Jakarta" })
    : "—";
}

export default function SettingsPage() {
  const [model, setModelState] = useState("");
  const [fallback, setFb] = useState(false);
  const [health, setHealth] = useState<any>(null);
  const [deliveries, setDeliveries] = useState<any>(null);
  const [deliveryError, setDeliveryError] = useState("");
  const [desktopAi, setDesktopAi] = useState<any>(null);
  const [desktopAiStatus, setDesktopAiStatus] = useState("");
  const isDesktop = typeof window !== "undefined" && window.parent !== window;

  useEffect(() => {
    setModelState(getModel() || "");
    setFb(getFallback());
    fetch("/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => {});
    if (window.parent !== window) window.parent.postMessage({ type: "stocks-desktop-load-ai" }, "*");
    const handler = (event: MessageEvent) => {
      if (event.data?.type === "stocks-desktop-ai-config") setDesktopAi(event.data.config);
      if (event.data?.type === "stocks-desktop-ai-saved") setDesktopAiStatus("Tersimpan. Tutup dan buka ulang aplikasi untuk menerapkan AI.");
      if (event.data?.type === "stocks-desktop-ai-error") setDesktopAiStatus(event.data.error);
    };
    window.addEventListener("message", handler);
    const load = () =>
      api
        .notificationStatus()
        .then(setDeliveries)
        .then(() => setDeliveryError(""))
        .catch(() => setDeliveryError("Delivery health unavailable."));
    load();
    const timer = window.setInterval(load, 30000);
    return () => { clearInterval(timer); window.removeEventListener("message", handler); };
  }, []);

  return (
    <div>
      <h1 className="page-title">Settings</h1>
      <div className="grid grid-2">
        <div className="card">
          <div className="card-title">AI Settings</div>
          <div style={{ marginBottom: 12 }}>
            <div className="muted" style={{ marginBottom: 4 }}>
              Default AI Model
            </div>
            <input
              value={model}
              onChange={(e) => setModelState(e.target.value)}
              disabled
              style={{
                background: "var(--panel2)",
                border: "1px solid var(--border)",
                color: "var(--text)",
                padding: "7px 10px",
                borderRadius: 6,
                width: "100%",
              }}
            />
            <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
              Ubah lewat selector model di top bar — preferensi disimpan di
              browser.
            </div>
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={fallback}
              onChange={(e) => {
                setFallback(e.target.checked);
                setFb(e.target.checked);
              }}
            />
            Allow AI fallback
          </label>
        </div>
        <div className="card">
          <div className="card-title">Infrastructure</div>
          <table>
            <tbody>
              <tr>
                <td className="muted">Backend API</td>
                <td>127.0.0.1:8200</td>
              </tr>
              <tr>
                <td className="muted">Frontend</td>
                <td>Next.js</td>
              </tr>
              <tr>
                <td className="muted">9Router</td>
                <td>127.0.0.1:20128</td>
              </tr>
              <tr>
                <td className="muted">Ollama</td>
                <td>127.0.0.1:11434 (localhost only)</td>
              </tr>
              <tr>
                <td className="muted">PostgreSQL</td>
                <td>127.0.0.1:5432 (db: stocks)</td>
              </tr>
              <tr>
                <td className="muted">Health</td>
                <td>
                  {health
                    ? `${health.status} · db ${health.database} · 9router ${health.nine_router} · ollama ${health.ollama}`
                    : "-"}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      {isDesktop && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-title">AI / 9ROUTER (OPTIONAL)</div>
          <p className="muted">Market data tetap berjalan tanpa AI. Simpan konfigurasi ini bila ingin memakai AI Research.</p>
          <div className="grid grid-2">
            <input placeholder="9Router URL (.../v1)" value={desktopAi?.nine_router_url || ""} onChange={(e) => setDesktopAi({ ...desktopAi, nine_router_url: e.target.value })} />
            <input type="password" placeholder="9Router API key" value={desktopAi?.nine_router_api_key || ""} onChange={(e) => setDesktopAi({ ...desktopAi, nine_router_api_key: e.target.value })} />
            <input placeholder="Model default" value={desktopAi?.default_model || ""} onChange={(e) => setDesktopAi({ ...desktopAi, default_model: e.target.value })} />
            <button className="btn btn-primary" onClick={() => { setDesktopAiStatus("Menyimpan..."); window.parent.postMessage({ type: "stocks-desktop-save-ai", config: desktopAi || {} }, "*"); }}>SAVE AI CONFIG</button>
          </div>
          {desktopAiStatus && <p className="muted" style={{ marginTop: 10 }}>{desktopAiStatus}</p>}
        </div>
      )}
      <DesktopPairing />
      <div className="card" style={{ marginTop: 12 }}>
        <div className="card-title">
          NOTIFICATION DELIVERY HEALTH · {deliveries?.owner || "HERMES"}
        </div>
        {deliveryError && <div className="terminal-error">{deliveryError}</div>}
        {!deliveries && !deliveryError && (
          <div className="terminal-loading">
            <span>LOADING DELIVERY STATUS</span>
          </div>
        )}
        {deliveries && (
          <div className="table-scroll">
            <table className="dense-table">
              <thead>
                <tr>
                  <th>TYPE</th>
                  <th>DATE / CYCLE</th>
                  <th>STATUS</th>
                  <th className="num">ATTEMPTS</th>
                  <th>DELIVERED</th>
                  <th>LAST ERROR</th>
                </tr>
              </thead>
              <tbody>
                {deliveries.data?.length ? (
                  deliveries.data.map((row: any) => (
                    <tr key={row.id}>
                      <td>{row.message_type}</td>
                      <td>
                        {row.target_date} · {row.cycle}
                      </td>
                      <td
                        className={
                          row.status === "SENT"
                            ? "pos"
                            : row.status === "FAILED"
                              ? "neg"
                              : ""
                        }
                      >
                        {row.status}
                      </td>
                      <td className="num">{row.attempt_count}</td>
                      <td>{stamp(row.sent_at)}</td>
                      <td className="neg">{row.last_error || "—"}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="terminal-empty">
                      NO DELIVERY RECORDS YET
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
