"use client";

import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { api } from "@/lib/api";

type UploadResult = { status: string; filename: string; bytes: number; tenant_id: string };

export default function AdminPage() {
  const [results, setResults] = useState<UploadResult[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const upload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setBusy(true);
    setErr(null);
    try {
      const out: UploadResult[] = [];
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        const r = (await api.upload(form)) as UploadResult;
        out.push(r);
      }
      setResults((prev) => [...out, ...prev]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold mb-1">Admin</h1>
        <p className="text-sm text-ink-500">
          Ingest new documents/media. Files are PII-scrubbed before embeddings hit the vector store.
        </p>
      </header>

      <section className="rounded-lg border border-dashed border-ink-300 dark:border-ink-700 bg-white dark:bg-ink-900 p-8 text-center">
        <Upload className="w-8 h-8 mx-auto text-ink-400 mb-2" />
        <input
          ref={fileRef}
          type="file"
          multiple
          onChange={(e) => upload(e.target.files)}
          className="block mx-auto text-sm"
          accept=".pdf,.txt,.md,.docx,.png,.jpg,.jpeg,.gif,.webp,.bmp,.mp4,.mov,.mkv,.webm,.wav,.mp3,.m4a,.flac,.ogg"
        />
        {busy && <p className="text-xs text-ink-500 mt-2">Uploading & queueing ingestion…</p>}
      </section>

      {err && <div className="text-rose-500 text-sm">{err}</div>}

      {results.length > 0 && (
        <section>
          <h2 className="text-sm font-medium mb-2">Recent uploads</h2>
          <ul className="space-y-2 text-sm">
            {results.map((r, i) => (
              <li
                key={i}
                className="rounded border border-ink-200 dark:border-ink-800 p-3 flex items-center justify-between"
              >
                <div>
                  <div className="font-medium">{r.filename}</div>
                  <div className="text-xs text-ink-500">tenant={r.tenant_id} · {r.bytes.toLocaleString()} bytes</div>
                </div>
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600">{r.status}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
