"use client";

import { Send, Sparkles } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "@/lib/api";

type Step = { node: string; detail?: Record<string, unknown> };

export default function ChatPage() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [steps, setSteps] = useState<Step[]>([]);
  const [done, setDone] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [citations, setCitations] = useState<{ source_uri: string; quote?: string | null }[]>([]);
  const [nli, setNli] = useState<number | null>(null);
  const stopRef = useRef<(() => void) | null>(null);

  const start = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!query.trim() || streaming) return;
    setAnswer("");
    setSteps([]);
    setCitations([]);
    setNli(null);
    setDone(false);
    setStreaming(true);
    stopRef.current?.();
    stopRef.current = api.streamChat(
      { query },
      ({ event, data }) => {
        if (event === "router") {
          setSteps((s) => [...s, { node: "router", detail: data }]);
        } else if (event === "retrieved") {
          setSteps((s) => [...s, { node: "retrieved", detail: data }]);
        } else if (event === "token") {
          setAnswer((prev) => prev + (data?.delta ?? ""));
        } else if (event === "critique") {
          setNli(typeof data?.nli === "number" ? data.nli : null);
          setSteps((s) => [...s, { node: "critique", detail: data }]);
        } else if (event === "done") {
          setCitations(data?.citations ?? []);
          setDone(true);
          setStreaming(false);
        }
      },
      () => setStreaming(false)
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6 max-w-6xl">
      <div className="space-y-4">
        <header>
          <h1 className="text-2xl font-semibold mb-1">Chat</h1>
          <p className="text-sm text-ink-500">
            Streaming agent: router → retrieve → rerank → generate → NLI critique.
          </p>
        </header>

        <form onSubmit={start} className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask your corpus a grounded question…"
            className="flex-1 px-3 py-2 rounded-md border border-ink-200 dark:border-ink-700 bg-white dark:bg-ink-900"
          />
          <button
            type="submit"
            disabled={streaming}
            className="px-4 py-2 rounded-md bg-brand text-white text-sm font-medium hover:bg-brand-600 disabled:opacity-50 flex items-center gap-1.5"
          >
            <Send className="w-4 h-4" />
            {streaming ? "Streaming…" : "Send"}
          </button>
        </form>

        <article className="rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 p-5 min-h-[200px]">
          {!answer && !streaming && (
            <p className="text-sm text-ink-400 italic">Answer will stream here.</p>
          )}
          <div className="whitespace-pre-wrap leading-relaxed">{answer}</div>
          {done && (
            <div className="mt-4 text-xs text-ink-500 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5" />
              {nli != null ? `NLI faithfulness: ${nli.toFixed(2)}` : "complete"}
            </div>
          )}
        </article>

        {citations.length > 0 && (
          <section>
            <h2 className="text-sm font-medium mb-2">Citations</h2>
            <ul className="space-y-2 text-sm">
              {citations.map((c, i) => (
                <li key={i} className="rounded border border-ink-200 dark:border-ink-800 p-2">
                  <div className="text-xs text-ink-500">{c.source_uri}</div>
                  {c.quote && <div className="mt-1 italic">“{c.quote}”</div>}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <aside className="space-y-3">
        <h2 className="text-sm font-medium">Agent steps</h2>
        <ol className="space-y-2 text-xs">
          {steps.map((s, i) => (
            <li key={i} className="rounded border border-ink-200 dark:border-ink-800 p-2">
              <div className="font-mono text-ink-400">{i + 1}. {s.node}</div>
              <pre className="text-[10px] whitespace-pre-wrap text-ink-600 dark:text-ink-300 mt-1">
                {JSON.stringify(s.detail, null, 2)}
              </pre>
            </li>
          ))}
          {streaming && <li className="text-ink-400 italic text-xs">…streaming</li>}
        </ol>
      </aside>
    </div>
  );
}
