import { ExternalLink } from "lucide-react";

import type { Source } from "@/lib/types";

// the pages a researched answer is based on (Google Search results that Gemini used)
export default function SourceList({ sources, label = "Sources" }: { sources?: Source[]; label?: string }) {
  if (!sources?.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-400">{label}</span>
      {sources.map((source) => (
        <a
          key={source.url}
          href={source.url}
          target="_blank"
          rel="noreferrer"
          title={source.title}
          className="inline-flex max-w-[12rem] items-center gap-1 rounded-full bg-stone-100 px-2 py-0.5 text-[11px] text-stone-600 transition hover:bg-stone-200 hover:text-ink-900"
        >
          <span className="truncate">{source.title}</span>
          <ExternalLink className="size-2.5 shrink-0" />
        </a>
      ))}
    </div>
  );
}
