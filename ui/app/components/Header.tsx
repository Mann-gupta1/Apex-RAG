"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function Header() {
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [llmHealthy, setLlmHealthy] = useState<boolean | null>(null);
  const [tenant, setTenant] = useState("default");

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const r = await api.get<{ status: string; llm_healthy: boolean }>("/health");
        if (cancelled) return;
        setHealthy(r.status === "ok");
        setLlmHealthy(r.llm_healthy);
      } catch {
        if (!cancelled) {
          setHealthy(false);
          setLlmHealthy(false);
        }
      }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="border-b border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 px-6 py-3 flex items-center justify-between">
      <div className="text-sm text-ink-500">Multi-Modal Enterprise Search</div>
      <div className="flex items-center gap-3 text-xs">
        <label className="flex items-center gap-1.5">
          <span className="text-ink-500">Tenant</span>
          <input
            value={tenant}
            onChange={(e) => {
              setTenant(e.target.value);
              if (typeof window !== "undefined") {
                window.localStorage.setItem("apex.tenant", e.target.value);
              }
            }}
            className="px-2 py-0.5 rounded border border-ink-200 dark:border-ink-700 bg-transparent w-24"
          />
        </label>
        <Pill ok={healthy} label="API" />
        <Pill ok={llmHealthy} label="LLM" />
      </div>
    </header>
  );
}

function Pill({ ok, label }: { ok: boolean | null; label: string }) {
  const color =
    ok === null ? "bg-ink-300" : ok ? "bg-emerald-500" : "bg-rose-500";
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-ink-100 dark:bg-ink-800">
      <span className={`w-1.5 h-1.5 rounded-full ${color}`} />
      {label}
    </span>
  );
}
