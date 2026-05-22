const PREFIX = "/proxy/api";

function tenantHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const t = window.localStorage.getItem("apex.tenant");
  return t ? { "X-Tenant-Id": t } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${PREFIX}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...tenantHeader(),
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  upload: async (form: FormData) => {
    const res = await fetch(`${PREFIX}/upload`, {
      method: "POST",
      body: form,
      headers: tenantHeader(),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  streamChat: (
    body: { query: string; tenant_id?: string },
    onEvent: (ev: { event: string; data: unknown }) => void,
    onError?: (err: unknown) => void
  ): (() => void) => {
    const ctrl = new AbortController();
    (async () => {
      try {
        const res = await fetch(`${PREFIX}/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...tenantHeader() },
          body: JSON.stringify(body),
          signal: ctrl.signal,
        });
        if (!res.ok || !res.body) throw new Error(await res.text());
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += dec.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";
          for (const part of parts) {
            const event = (part.match(/^event:\s*(.*)$/m)?.[1] ?? "message").trim();
            const data = part.match(/^data:\s*(.*)$/m)?.[1];
            if (!data) continue;
            try {
              onEvent({ event, data: JSON.parse(data) });
            } catch {
              onEvent({ event, data });
            }
          }
        }
      } catch (err) {
        onError?.(err);
      }
    })();
    return () => ctrl.abort();
  },
};

export type RetrievedChunk = {
  chunk: {
    id: string;
    modality: "text" | "image" | "video" | "audio";
    content: string;
    context_summary?: string | null;
    provenance: {
      source_uri: string;
      page?: number | null;
      timestamp_start?: number | null;
      timestamp_end?: number | null;
      speaker?: string | null;
    };
  };
  score: number;
  fusion_rank?: number | null;
};

export type SearchResponse = {
  query: string;
  rewritten_queries: string[];
  results: RetrievedChunk[];
  latency_ms: number;
  cache_hit?: boolean;
};

export type Citation = {
  chunk_id: string;
  source_uri: string;
  modality: "text" | "image" | "video" | "audio";
  quote?: string | null;
  page?: number | null;
  timestamp_start?: number | null;
};

export type ChatResponse = {
  answer: string;
  citations: Citation[];
  faithfulness?: number | null;
  steps?: { node: string; detail: Record<string, unknown> }[];
  latency_ms: number;
};
