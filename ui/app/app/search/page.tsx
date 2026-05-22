"use client";

import { useState } from "react";
import { Search } from "lucide-react";
import { api, type SearchResponse, type RetrievedChunk } from "@/lib/api";
import { ResultCard } from "@/components/ResultCard";

const MODALITIES = ["text", "image", "video", "audio"] as const;

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [modalities, setModalities] = useState<string[]>([]);
  const [topK, setTopK] = useState(6);
  const [useRerank, setUseRerank] = useState(true);
  const [useHyde, setUseHyde] = useState(true);
  const [resp, setResp] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setErr(null);
    try {
      const data = await api.post<SearchResponse>("/search", {
        query,
        top_k: topK,
        modalities: modalities.length ? modalities : null,
        use_rerank: useRerank,
        use_hyde: useHyde,
      });
      setResp(data);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold mb-1">Search</h1>
        <p className="text-sm text-ink-500">
          Hybrid (dense + BM25 + RRF) with optional HyDE rewriting and cross-encoder rerank.
        </p>
      </header>

      <form onSubmit={submit} className="space-y-3">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-ink-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask anything across documents, images, video and audio…"
              className="w-full pl-9 pr-3 py-2 rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 rounded-md bg-brand text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50"
          >
            {loading ? "Searching…" : "Search"}
          </button>
        </div>

        <div className="flex items-center flex-wrap gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            {MODALITIES.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() =>
                  setModalities((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]))
                }
                className={`px-2 py-1 rounded border ${
                  modalities.includes(m)
                    ? "bg-brand/10 border-brand text-brand-700 dark:text-brand"
                    : "border-ink-200 dark:border-ink-700"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-1">
            top_k
            <input
              type="number"
              value={topK}
              min={1}
              max={50}
              onChange={(e) => setTopK(parseInt(e.target.value || "6", 10))}
              className="w-14 px-2 py-0.5 rounded border border-ink-200 dark:border-ink-700 bg-transparent"
            />
          </label>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={useRerank}
              onChange={(e) => setUseRerank(e.target.checked)}
            />
            rerank
          </label>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={useHyde}
              onChange={(e) => setUseHyde(e.target.checked)}
            />
            HyDE
          </label>
        </div>
      </form>

      {err && <div className="text-rose-500 text-sm">{err}</div>}

      {resp && (
        <section className="space-y-3">
          <div className="text-xs text-ink-500">
            {resp.results.length} results · {resp.latency_ms} ms
            {resp.rewritten_queries.length > 0 && (
              <> · rewrites: {resp.rewritten_queries.map((q, i) => (
                <span key={i} className="code mr-1">{q.slice(0, 40)}…</span>
              ))}</>
            )}
          </div>
          <ul className="space-y-3">
            {resp.results.map((r: RetrievedChunk, i: number) => (
              <ResultCard key={r.chunk.id || i} hit={r} index={i + 1} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
