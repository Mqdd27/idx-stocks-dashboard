"use client";

import { useEffect, useState } from "react";
import { api, type AIConfig } from "@/lib/api";
import { getModel, setModel } from "@/lib/store";

interface Props {
  onChange?: (model: string, local: boolean) => void;
}

export default function ModelSelector({ onChange }: Props) {
  const [models, setModels] = useState<AIConfig[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [local, setLocal] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    load();
  }, []);

  function load() {
    api.aiModels().then((m) => {
      setModels(m);
      const saved = getModel();
      const valid = m.find((x) => x.id === saved);
      const first = m[0];
      if (valid) {
        setSelected(valid.id);
        setLocal(valid.local);
      } else if (first) {
        setSelected(first.id);
        setLocal(first.local);
        setModel(first.id);
      }
    }).catch(() => {
      setModels([{ id: "qwen3.5:2b", name: "Qwen Local", provider: "ollama", local: true }]);
      setSelected("qwen3.5:2b");
      setLocal(true);
    });
  }

  function refresh() {
    setRefreshing(true);
    api.aiModels().then((m) => {
      setModels(m);
      const cur = getModel();
      const still = m.find((x) => x.id === cur);
      if (still) {
        setSelected(still.id);
        setLocal(still.local);
      }
    }).catch(() => {}).finally(() => setRefreshing(false));
  }

  function select(id: string) {
    setSelected(id);
    const m = models.find((x) => x.id === id);
    if (m) {
      setLocal(m.local);
      setModel(id);
      onChange?.(id, m.local);
    }
  }

  const localModels = models.filter((m) => m.local);
  const cloudModels = models.filter((m) => !m.local);
  const current = models.find((m) => m.id === selected);

  return (
    <div className="model-chip" title="AI Model">
      <select value={selected} onChange={(e) => select(e.target.value)}>
        {localModels.length > 0 && <optgroup label="LOCAL">{localModels.map((m) => (
          <option key={m.id} value={m.id}>{m.name}</option>
        ))}</optgroup>}
        {cloudModels.length > 0 && <optgroup label="CLOUD">{cloudModels.map((m) => (
          <option key={m.id} value={m.id}>{(m.usable === false) ? `${m.name} (tidak tersedia)` : m.name}</option>
        ))}</optgroup>}
      </select>
      <button className="btn btn-xs" onClick={refresh} disabled={refreshing} title="Refresh model list">
        {refreshing ? "…" : "↻"}
      </button>
      <span className={`badge ${local ? "local" : "cloud"}`}>{local ? "LOCAL" : "CLOUD"}</span>
      {current && current.provider === "9router" && <span className="muted" style={{ fontSize: 10 }}>via 9Router</span>}
    </div>
  );
}