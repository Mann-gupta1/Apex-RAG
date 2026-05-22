"use client";

import { ThumbsUp, ThumbsDown, FileText, Image as ImageIcon, Film, AudioLines } from "lucide-react";
import { useState } from "react";
import { api, type RetrievedChunk } from "@/lib/api";

const icons = {
  text: FileText,
  image: ImageIcon,
  video: Film,
  audio: AudioLines,
};

export function ResultCard({ hit, index }: { hit: RetrievedChunk; index: number }) {
  const Icon = icons[hit.chunk.modality] ?? FileText;
  const [submitted, setSubmitted] = useState<number | null>(null);

  const submit = async (rating: number) => {
    setSubmitted(rating);
    try {
      await api.post("/feedback", {
        query: typeof window !== "undefined" ? window.localStorage.getItem("apex.lastQuery") ?? "" : "",
        response: hit.chunk.content,
        chunk_ids: [hit.chunk.id],
        rating,
      });
    } catch {
      setSubmitted(null);
    }
  };

  const prov = hit.chunk.provenance;
  const locator = prov.page
    ? `p. ${prov.page}`
    : prov.timestamp_start != null
    ? `t=${prov.timestamp_start.toFixed(1)}s`
    : "";

  return (
    <li className="rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 p-4">
      <div className="flex items-center justify-between text-xs text-ink-500 mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-ink-400">#{index}</span>
          <Icon className="w-3.5 h-3.5" />
          <span className="font-mono">{hit.chunk.modality}</span>
          {locator && <span>· {locator}</span>}
          <span className="text-ink-400 truncate max-w-md">· {prov.source_uri}</span>
        </div>
        <span className="font-mono">score {hit.score.toFixed(3)}</span>
      </div>
      {hit.chunk.context_summary && (
        <div className="text-xs italic text-ink-500 mb-1">{hit.chunk.context_summary}</div>
      )}
      <div className="text-sm whitespace-pre-wrap">{hit.chunk.content.slice(0, 600)}{hit.chunk.content.length > 600 && "…"}</div>
      <div className="mt-3 flex items-center gap-2 text-xs">
        <button
          onClick={() => submit(1)}
          disabled={submitted !== null}
          className={`flex items-center gap-1 px-2 py-1 rounded border ${
            submitted === 1
              ? "bg-emerald-500/10 border-emerald-500 text-emerald-600"
              : "border-ink-200 dark:border-ink-700 hover:bg-ink-50 dark:hover:bg-ink-800"
          }`}
        >
          <ThumbsUp className="w-3 h-3" /> useful
        </button>
        <button
          onClick={() => submit(-1)}
          disabled={submitted !== null}
          className={`flex items-center gap-1 px-2 py-1 rounded border ${
            submitted === -1
              ? "bg-rose-500/10 border-rose-500 text-rose-600"
              : "border-ink-200 dark:border-ink-700 hover:bg-ink-50 dark:hover:bg-ink-800"
          }`}
        >
          <ThumbsDown className="w-3 h-3" /> not useful
        </button>
      </div>
    </li>
  );
}
