"use client";

import { useEffect, useRef, useState } from "react";
import ModelSelector from "./ModelSelector";
import { getFallback, getModel, setFallback } from "@/lib/store";
import { api } from "@/lib/api";

interface Props {
  symbol?: string;
  companyName?: string;
  drawer?: boolean;
}

interface Msg {
  role: "user" | "assistant";
  content: string;
  model?: string;
}

interface FallbackInfo {
  message: string;
  model: string;
  provider: string;
  text: string;
}

export default function AIAssistPanel({ symbol, companyName, drawer = false }: Props) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [queued, setQueued] = useState(false);
  const [convId, setConvId] = useState<number | null>(null);
  const [fb, setFb] = useState<FallbackInfo | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(true);
  const modelRef = useRef<string>("");
  const fallbackRef = useRef(getFallback());

  useEffect(() => {
    setMessages([]);
    setConvId(null);
    setFb(null);
  }, [symbol]);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight });
  }, [messages, busy]);

  function checkQueue() {
    fetch("/api/ai/queue-status")
      .then((r) => r.json())
      .then((j) => setQueued(j.active && j.queued > 0))
      .catch(() => {});
  }

  async function send(overrideModel?: string) {
    const text = input.trim();
    if (!text || busy) return;
    const model = overrideModel || getModel() || "qwen3.5:2b";
    setInput("");
    setFb(null);
    const msgs = [...messages, { role: "user" as const, content: text, model }];
    if (modelRef.current && modelRef.current !== model) {
      msgs.push({ role: "assistant" as const, content: `— Model changed: ${modelRef.current} → ${model} —`, model });
    }
    setMessages(msgs);
    modelRef.current = model;
    await doSend(text, model);
  }

  async function doSend(text: string, model: string) {
    setBusy(true);
    try {
      const resp = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, model, symbol: symbol || null, conversation_id: convId, stream: true }),
      });
      if (!resp.ok) {
        const j = await resp.json().catch(() => ({}));
        handleErr(j, model, text);
        return;
      }
      const reader = resp.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let acc = "";
      setMessages((m) => [...m, { role: "assistant", content: "", model }]);
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const lines = decoder.decode(value, { stream: true }).split("\n");
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          let payload: any;
          try {
            payload = JSON.parse(line.slice(5).trim());
          } catch {
            continue;
          }
          if (payload.delta) {
            acc += payload.delta;
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { role: "assistant", content: acc, model };
              return copy;
            });
          } else if (payload.error) {
            handleErr(payload, model, text);
            return;
          } else if (payload.done) {
            setConvId(payload.conversation_id ?? null);
          }
        }
      }
    } catch (e: any) {
      setFb({ message: String(e.message || e), model, provider: "unknown", text });
    } finally {
      setBusy(false);
      checkQueue();
    }
  }

  function handleErr(j: any, model: string, text: string) {
    if (j.error) {
      const info: FallbackInfo = { message: String(j.error), model, provider: j.provider || "unknown", text };
      setFb(info);
      if (fallbackRef.current && j.fallback_available) {
        api.cloudFallbackModel().then((cloudModel) => {
          setMessages((m) => [...m, { role: "assistant", content: `— ${model} gagal. Auto-fallback: ${cloudModel} —`, model }]);
          modelRef.current = cloudModel;
          setTimeout(() => doSendWithText(model, cloudModel), 0);
        });
      }
    }
  }

  async function doSendWithText(model: string, text: string) {
    setFb(null);
    await doSend(text, model);
  }

  const header = (
    <div className="chat-head">
      <div className="chat-title"><strong>Ask AI</strong>{companyName && <span title={companyName}>{companyName}</span>}</div>
      <div className="chat-model"><span>Model</span><ModelSelector /></div>
    </div>
  );

  const fallbackBox = fb && (
    <div className="analysis-err">
      <div style={{ marginBottom: 8 }}>{fb.message}</div>
      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>
        {fb.provider} · Fallback available: cloud model
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn btn-sm" onClick={() => { setFb(null); doSendWithText(fb.model, fb.text); }}>Retry Local</button>
        <button className="btn btn-sm btn-primary" onClick={() => { api.cloudFallbackModel().then((m) => { setFb(null); modelRef.current = m; setMessages((prev) => [...prev, { role: "assistant", content: `— Model changed: ${fb.model} → ${m} —`, model: m }]); doSendWithText(m, fb.text); }); }}>Use Cloud</button>
      </div>
    </div>
  );

  const body = (
    <div className="chat-body" ref={bodyRef}>
      {messages.length === 0 && (
        <div className="empty-state">
          Tanya tentang {symbol ? symbol : "saham"} — mis. "Kenapa ROE turun?" atau "Jelaskan MACD sekarang."
        </div>
      )}
      {queued && <div className="queue-note">Local AI is busy. Your request is queued.</div>}
      {messages.map((m, i) => (
        <div key={i} className={`chat-msg ${m.role}`}>
          <div className="who">{m.role === "user" ? "You" : `AI${m.model ? " · " + m.model : ""}`}</div>
          <div className="bubble">{m.role === "assistant" ? <ChatMarkdown text={m.content || (busy && i === messages.length - 1 ? "▍" : "")} /> : m.content}</div>
        </div>
      ))}
      {busy && messages[messages.length - 1]?.role === "user" && <div className="typing">Menganalisis…</div>}
      {fallbackBox}
    </div>
  );

  const inputRow = (
    <div className="chat-input-row">
      <input
        placeholder={symbol ? `Ask about ${symbol}…` : "Ask about the market…"}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && send()}
      />
      <button className="btn btn-primary" onClick={() => send()} disabled={busy || !input.trim()}>Send</button>
    </div>
  );

  if (!drawer) {
    return (
      <div className="chat-panel">
        {header}
        {body}
        {inputRow}
      </div>
    );
  }

  return (
    <>
      <button className="drawer-toggle" onClick={() => setOpen(!open)} title="AI Assistant">✦</button>
      {open && (
        <div className="chat-drawer">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", borderBottom: "1px solid var(--border)" }}>
            <strong>AI Assistant{companyName ? ` · ${companyName}` : ""}</strong>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <label style={{ fontSize: 11, color: "var(--muted)", display: "flex", gap: 4, alignItems: "center" }}>
                <input type="checkbox" defaultChecked={fallbackRef.current} onChange={(e) => { fallbackRef.current = e.target.checked; setFallback(e.target.checked); }} />
                Allow AI fallback
              </label>
              <ModelSelector />
              <button className="btn btn-sm" onClick={() => setOpen(false)}>✕</button>
            </div>
          </div>
          {body}
          {inputRow}
        </div>
      )}
    </>
  );
}
function ChatMarkdown({ text }: { text: string }) {
  return <div className="chat-markdown">{text.split("\n").map((line, i) => {
    const v = line.trim();
    if (!v) return <div className="markdown-gap" key={i} />;
    if (/^---+$/.test(v)) return <hr key={i} />;
    if (/^#{1,6}\s/.test(v)) return <h3 key={i}>{chatInline(v.replace(/^#{1,6}\s/, ""))}</h3>;
    if (/^[-*]\s/.test(v)) return <div className="markdown-item" key={i}>• {chatInline(v.slice(2))}</div>;
    if (/^\d+\.\s/.test(v)) return <div className="markdown-item" key={i}>{chatInline(v)}</div>;
    return <p key={i}>{chatInline(v)}</p>;
  })}</div>;
}
function chatInline(value: string) {
  return value.split(/(\*\*[^*]+\*\*)/g).map((part, i) => part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part);
}
