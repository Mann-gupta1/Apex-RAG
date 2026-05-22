"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Metrics = Record<string, number>;

export default function EvalPage() {
  const [running, setRunning] = useState(false);
  const [latest, setLatest] = useState<Metrics | null>(null);
  const [baseline, setBaseline] = useState<Metrics | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const trigger = async (variant: string) => {
    setRunning(true);
    setErr(null);
    try {
      await api.post(`/eval?variant=${variant}`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => {
    setBaseline({
      faithfulness: 0.85,
      context_recall: 0.8,
      context_precision: 0.78,
      answer_relevance: 0.86,
      answer_correctness: 0.74,
    });
    setLatest({
      faithfulness: 0.89,
      context_recall: 0.84,
      context_precision: 0.79,
      answer_relevance: 0.88,
      answer_correctness: 0.77,
    });
  }, []);

  return (
    <div className="max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold mb-1">Eval</h1>
        <p className="text-sm text-ink-500">
          RAGAS metrics, regression history, and drift detection.
        </p>
      </header>

      <div className="flex items-center gap-2">
        <button
          onClick={() => trigger("apex")}
          disabled={running}
          className="px-3 py-1.5 rounded-md bg-brand text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50"
        >
          {running ? "Queued…" : "Run Apex eval"}
        </button>
        <button
          onClick={() => trigger("naive")}
          disabled={running}
          className="px-3 py-1.5 rounded-md border border-ink-200 dark:border-ink-700 text-sm hover:bg-ink-50 dark:hover:bg-ink-800"
        >
          Run Naive eval
        </button>
      </div>
      {err && <div className="text-rose-500 text-sm">{err}</div>}

      <section className="rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 p-5">
        <h2 className="text-sm font-medium mb-3">Metrics (illustrative until run)</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-ink-500">
              <th className="py-1">Metric</th>
              <th>Baseline</th>
              <th>Latest</th>
              <th>Δ</th>
            </tr>
          </thead>
          <tbody>
            {latest && baseline &&
              Object.keys(latest).map((m) => {
                const b = baseline[m] ?? 0;
                const v = latest[m] ?? 0;
                const d = v - b;
                return (
                  <tr key={m} className="border-t border-ink-100 dark:border-ink-800">
                    <td className="py-2 font-mono text-xs">{m}</td>
                    <td>{b.toFixed(3)}</td>
                    <td>{v.toFixed(3)}</td>
                    <td className={d >= 0 ? "text-emerald-600" : "text-rose-600"}>{d >= 0 ? "+" : ""}{d.toFixed(3)}</td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </section>

      <section className="rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 p-5">
        <h2 className="text-sm font-medium mb-2">Phoenix traces</h2>
        <p className="text-sm text-ink-500">
          Open the live Phoenix UI for per-request traces:
          <a
            href="http://localhost:6006"
            target="_blank"
            rel="noreferrer"
            className="ml-2 text-brand hover:underline"
          >
            http://localhost:6006
          </a>
        </p>
      </section>
    </div>
  );
}
