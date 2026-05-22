import Link from "next/link";

export default function HomePage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-3xl font-semibold mb-3">Apex RAG</h1>
      <p className="text-ink-600 dark:text-ink-300 mb-6">
        Multi-Modal Enterprise Search — text, image, video, audio. Hybrid retrieval,
        cross-encoder reranking, LangGraph agent, RAGAS evaluation.
      </p>
      <div className="grid sm:grid-cols-2 gap-4">
        {[
          { href: "/search", title: "Search", desc: "Hybrid + rerank with modality filters and score breakdowns." },
          { href: "/chat", title: "Chat", desc: "Streaming agent with inline citations and faithfulness score." },
          { href: "/eval", title: "Eval", desc: "RAGAS dashboard, regression history, drift detection." },
          { href: "/admin", title: "Admin", desc: "Upload pipeline, ingestion jobs, audit log viewer." },
        ].map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="block rounded-lg border border-ink-200 dark:border-ink-800 bg-white dark:bg-ink-900 p-5 hover:border-brand transition-colors"
          >
            <div className="text-lg font-medium">{card.title}</div>
            <div className="text-sm text-ink-500 mt-1">{card.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
