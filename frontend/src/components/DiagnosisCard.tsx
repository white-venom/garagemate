"use client";

import { ArrowRight, CalendarPlus, CircleCheck, Lightbulb, OctagonAlert, Sparkles, Wrench } from "lucide-react";

import { CategoryIcon } from "@/lib/categories";
import { formatPriceRange, severityStyles } from "@/lib/format";
import type { Diagnosis, Severity } from "@/lib/types";

interface DiagnosisCardProps {
  diagnosis: Diagnosis;
  booked: boolean;
  onBook: () => void;
}

const LEVELS: Severity[] = ["low", "medium", "high", "critical"];
const LEVEL_COLORS = ["#10b981", "#f59e0b", "#f97316", "#dc2626"];

function point(angle: number, radius: number) {
  const radians = (angle * Math.PI) / 180;
  return { x: 50 + radius * Math.cos(radians), y: 50 - radius * Math.sin(radians) };
}

// little semicircle gauge, needle points at the severity
function SeverityGauge({ severity }: { severity: Severity }) {
  const level = LEVELS.indexOf(severity);
  const needle = point(180 - (level * 45 + 22.5), 30);
  return (
    <svg viewBox="0 0 100 58" className="w-24 shrink-0" aria-label={`Severity: ${severity}`}>
      {LEVELS.map((_, index) => {
        const start = point(180 - index * 45 - 2, 40);
        const end = point(180 - (index + 1) * 45 + 2, 40);
        return (
          <path
            key={index}
            d={`M ${start.x} ${start.y} A 40 40 0 0 1 ${end.x} ${end.y}`}
            fill="none"
            stroke={LEVEL_COLORS[index]}
            strokeWidth="8"
            opacity={index === level ? 1 : 0.28}
          />
        );
      })}
      <line x1="50" y1="50" x2={needle.x} y2={needle.y} stroke="white" strokeWidth="3" strokeLinecap="round" />
      <circle cx="50" cy="50" r="4.5" fill="white" />
    </svg>
  );
}

export default function DiagnosisCard({ diagnosis, booked, onBook }: DiagnosisCardProps) {
  const severity = severityStyles[diagnosis.severity];
  const service = diagnosis.recommended_service;

  return (
    <article className="overflow-hidden rounded-2xl rounded-tl-md bg-white shadow-[0_12px_32px_-16px_rgb(0_0_0/0.25)] ring-1 ring-stone-200/80">
      <header className="flex items-start gap-3 bg-ink-900 px-5 pb-4 pt-5 text-white">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-brand-400">
            <CategoryIcon category={diagnosis.category} className="size-3.5" /> Inspection report · {diagnosis.category_label}
          </p>
          <h3 className="mt-2 font-display text-xl font-semibold leading-tight tracking-tight">{diagnosis.title}</h3>
          <p className="mt-1.5 font-mono text-[11px] text-stone-400">
            #D-{String(diagnosis.id).padStart(5, "0")} ·{" "}
            {new Date(diagnosis.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
          </p>
        </div>
        <div className="flex flex-col items-center">
          <SeverityGauge severity={diagnosis.severity} />
          <span className="-mt-0.5 text-[10px] font-bold uppercase tracking-[0.14em] text-stone-300">{severity.label}</span>
        </div>
      </header>

      {diagnosis.safe_to_drive ? (
        <p className="flex items-center gap-2 bg-emerald-50 px-5 py-2 text-xs font-medium text-emerald-800">
          <CircleCheck className="size-4" /> OK for short, careful drives. Get it checked soon.
        </p>
      ) : (
        <p className="flex items-center gap-2 bg-red-50 px-5 py-2 text-xs font-medium text-red-800">
          <OctagonAlert className="size-4" /> Avoid driving until a mechanic has checked it.
        </p>
      )}

      <div className="space-y-5 px-5 py-5">
        <p className="text-[14px] leading-relaxed text-ink-800">{diagnosis.summary}</p>

        {diagnosis.probable_causes.length > 0 && (
          <section>
            <h4 className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Likely causes</h4>
            <ol className="mt-3 space-y-3">
              {diagnosis.probable_causes.map((cause, index) => {
                const percent = Math.round(cause.likelihood * 100);
                return (
                  <li key={cause.name} className="flex gap-3">
                    <span className="w-5 pt-px font-mono text-xs text-stone-400">0{index + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex justify-between gap-3 text-[13px]">
                        <span className={index === 0 ? "font-semibold text-ink-900" : "text-ink-800"}>{cause.name}</span>
                        <span className="shrink-0 font-mono tabular-nums text-stone-500">{percent}%</span>
                      </div>
                      <div className="mt-1.5 h-1.5 rounded-full bg-stone-100">
                        <div
                          className={`h-1.5 rounded-full ${index === 0 ? "bg-brand-500" : "bg-stone-400"}`}
                          style={{ width: `${Math.max(percent, 3)}%` }}
                        />
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
        )}

        {service && (
          <section className="rounded-xl border border-stone-200 bg-stone-50/70 p-4">
            <div className="flex items-start gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-500 text-ink-950">
                <Wrench className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Recommended</p>
                <p className="mt-0.5 font-semibold text-ink-900">{service.name}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-stone-600">{service.description}</p>
              </div>
            </div>
            <div className="mt-3 flex items-baseline justify-between border-t border-dashed border-stone-300 pt-3">
              <span className="text-xs text-stone-500">Estimated cost</span>
              <span className="font-display text-lg font-semibold text-ink-900">
                {formatPriceRange(diagnosis.estimated_cost_min, diagnosis.estimated_cost_max)}
              </span>
            </div>
          </section>
        )}

        {diagnosis.advice && (
          <p className="flex gap-2.5 rounded-xl bg-amber-50/70 px-3.5 py-3 text-[13px] leading-relaxed text-amber-950">
            <Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-500" />
            {diagnosis.advice}
          </p>
        )}
      </div>

      <footer className="flex flex-col gap-3 border-t border-stone-100 bg-stone-50/60 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="flex items-center gap-1.5 text-[11px] text-stone-500">
          {diagnosis.source === "ai" && <Sparkles className="size-3 text-violet-500" />}
          {diagnosis.source === "ai" ? "Rule engine + Gemini second opinion" : "Based on our symptom checklist"}. Final
          call after inspection.
        </p>
        <button
          type="button"
          onClick={onBook}
          className="group inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-ink-950 shadow-[0_8px_20px_-10px] shadow-brand-600 transition hover:bg-brand-400"
        >
          <CalendarPlus className="size-4" /> {booked ? "Book another visit" : "Book a mechanic"}
          <ArrowRight className="size-4 transition group-hover:translate-x-0.5" />
        </button>
      </footer>
    </article>
  );
}
