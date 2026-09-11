"use client";

import { useState } from "react";

export default function DesktopPairing() {
  const [code, setCode] = useState("");
  const [expires, setExpires] = useState(0);
  const [error, setError] = useState("");

  async function create() {
    setError("");
    const response = await fetch("/api/desktop/pairings", { method: "POST" });
    if (!response.ok) {
      setError("Unlock admin web session before creating a desktop pairing code.");
      return;
    }
    const data = await response.json();
    setCode(data.code);
    setExpires(data.expires_in_seconds);
  }

  return <div className="card" style={{ marginTop: 12 }}><div className="card-title">DESKTOP PAIRING</div><p className="muted">Create a one-time code for a new desktop app. The code expires after 10 minutes and is not an admin token.</p><button className="btn" onClick={create}>CREATE PAIRING CODE</button>{code && <div className="analysis-box" style={{ marginTop: 10 }}><strong>{code}</strong><div className="muted">Enter this code in the desktop app within {Math.ceil(expires / 60)} minutes. It can only be redeemed once.</div></div>}{error && <div className="terminal-error" style={{ marginTop: 10 }}>{error}</div>}</div>;
}
