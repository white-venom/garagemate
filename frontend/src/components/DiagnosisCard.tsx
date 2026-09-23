"use client";

import { CalendarPlus, CheckCircle2, Lightbulb, OctagonAlert, Wrench } from "lucide-react";

import { formatPriceRange, severityStyles } from "@/lib/format";
import type { Diagnosis } from "@/lib/types";

interface DiagnosisCardProps {
  diagnosis: Diagnosis;
  booked: boolean;
  onBook: () => void;
}

export default function DiagnosisCard({ diagnosis, booked, onBook }: DiagnosisCardProps) {
  const severity = severityStyles[diagnosis.severity];
  const service = diagnosis.recommended_service;

  return (
    <article className="overflow-hidden rounded-2xl rounded-tl-sm bg-white shadow-sm ring-1 ring-stone-200">
      <div className={`h-1.5 ${severity.bar}`} />

      <div className="space-y-4 p-4 sm:p-5">
        <header>
          <p className="text-xs font-medium uppercase tracking-wide text-stone-500">
            Diagnosis · {diagnosis.category_label}
          </p>
          <h3 className="mt-1 text-lg font-semibold leading-snug text-stone-900">{diagnosis.title}</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${severity.badge}`}>
              {severity.label} severity
            </span>
            {diagnosis.safe_to_drive ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
                <CheckCircle2 className="size-3.5" /> OK for short, careful drives
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700 ring-1 ring-red-200">
                <OctagonAlert className="size-3.5" /> Avoid driving until checked
              </span>
            )}
          </div>
        </header>

        <p className="text-sm leading-relaxed text-stone-700">{diagnosis.summary}</p>

        {diagnosis.probable_causes.length > 0 && (
          <section>
            <h4 className="text-xs font-semibold uppercase tracking-wide text-stone-500">Likely causes</h4>
            <ul className="mt-2 space-y-2">
              {diagnosis.probable_causes.map((cause) => {
                const percent = Math.round(cause.likelihood * 100);
                return (
                  <li key={cause.name}>
                    <div className="flex justify-between gap-3 text-sm">
                      <span className="text-stone-800">{cause.name}</span>
                      <span className="shrink-0 tabular-nums text-stone-500">{percent}%</span>
                    </div>
                    <div className="mt-1 h-1.5 rounded-full bg-stone-100">
                      <div className="h-1.5 rounded-full bg-stone-700" style={{ width: `${Math.max(percent, 3)}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {service && (
          <section className="flex items-start gap-3 rounded-xl bg-stone-50 p-3 ring-1 ring-stone-200">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-amber-100 text-amber-800">
              <Wrench className="size-4" />
            </span>
            <div className="min-w-0 text-sm">
              <p className="font-semibold text-stone-900">{service.name}</p>
              <p className="text-stone-600">{service.description}</p>
              <p className="mt-1 font-medium text-stone-900">
                {formatPriceRange(diagnosis.estimated_cost_min, diagnosis.estimated_cost_max)}
                <span className="font-normal text-stone-500"> · final price after inspection</span>
              </p>
            </div>
          </section>
        )}

        {diagnosis.advice && (
          <p className="flex gap-2 text-sm text-stone-700">
            <Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-500" />
            {diagnosis.advice}
          </p>
        )}

        <div className="flex flex-col gap-2 border-t border-stone-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-stone-400">
            {diagnosis.source === "ai" ? "Rule engine + Gemini second opinion" : "Based on our symptom checklist"}.
            A mechanic will confirm on inspection.
          </p>
          <button
            type="button"
            onClick={onBook}
            className="inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-stone-900 transition hover:bg-amber-400"
          >
            <CalendarPlus className="size-4" /> {booked ? "Book another visit" : "Book a mechanic"}
          </button>
        </div>
      </div>
    </article>
  );
}
