"use client";

import { Activity, CalendarPlus, Check, Menu, Stethoscope } from "lucide-react";

import { CategoryIcon } from "@/lib/categories";
import { formatPlate } from "@/lib/format";
import type { Conversation, Stage } from "@/lib/types";

interface ChatHeaderProps {
  conversation: Conversation | null;
  busy: boolean;
  aiTrouble: boolean;
  onOpenMenu: () => void;
  onDiagnose: () => void;
  onBook: () => void;
  onOpenLogs: () => void;
}

const STEPS = ["Describe", "Questions", "Diagnosis", "Booking"];
const STEP_INDEX: Record<Stage, number> = { new: 0, gathering: 1, diagnosed: 2, booked: 4 };

// the car as an Indian style number plate chip
export function NumberPlate({ label }: { label: string }) {
  return (
    <span className="inline-flex items-stretch overflow-hidden rounded-[5px] border border-ink-900/80 bg-white font-mono text-[10.5px] font-semibold uppercase leading-none tracking-wider text-ink-900 shadow-sm">
      <span className="flex items-center bg-sky-700 px-1 text-[7px] text-white">IND</span>
      <span className="px-1.5 py-1">{label}</span>
    </span>
  );
}

function Stepper({ stage }: { stage: Stage }) {
  const current = STEP_INDEX[stage];
  return (
    <ol className="hidden items-center gap-1.5 lg:flex" aria-label="Progress">
      {STEPS.map((step, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li key={step} className="flex items-center gap-1.5">
            <span
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition ${
                active ? "bg-ink-900 text-white" : done ? "text-ink-900" : "text-stone-400"
              }`}
            >
              <span
                className={`grid size-4 place-items-center rounded-full text-[9px] ${
                  active ? "bg-brand-500 text-ink-950" : done ? "bg-emerald-500 text-white" : "bg-stone-200 text-stone-500"
                }`}
              >
                {done ? <Check className="size-2.5" strokeWidth={3} /> : index + 1}
              </span>
              {step}
            </span>
            {index < STEPS.length - 1 && <span className={`h-px w-4 ${done ? "bg-emerald-500" : "bg-stone-300"}`} />}
          </li>
        );
      })}
    </ol>
  );
}

export default function ChatHeader({ conversation, busy, aiTrouble, onOpenMenu, onDiagnose, onBook, onOpenLogs }: ChatHeaderProps) {
  const vehicle = conversation
    ? [conversation.vehicle.year, conversation.vehicle.make, conversation.vehicle.model].filter(Boolean).join(" ")
    : "";
  const plate = conversation?.vehicle.registration_number ? formatPlate(conversation.vehicle.registration_number) : "";
  const canDiagnose = conversation?.stage === "gathering" && Boolean(conversation.issue_category);
  const canBook = conversation?.stage === "diagnosed" || conversation?.stage === "booked";
  const stage = conversation?.stage ?? "new";
  const progress = Math.min(STEP_INDEX[stage], 3) / 3;

  return (
    <header className="relative border-b border-stone-200/80 bg-white/85 backdrop-blur">
      <div className="flex items-center gap-3 px-4 py-3">
        <button
          type="button"
          onClick={onOpenMenu}
          className="-ml-1 rounded-lg p-1.5 text-stone-600 hover:bg-stone-100 md:hidden"
          aria-label="Open conversation history"
        >
          <Menu className="size-5" />
        </button>

        <span className="hidden size-9 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600 ring-1 ring-brand-100 sm:grid">
          <CategoryIcon category={conversation?.issue_category} className="size-[18px]" />
        </span>

        <div className="min-w-0 flex-1">
          <h1 className="truncate font-display text-[15px] font-semibold tracking-tight text-ink-900 sm:text-base">
            {conversation?.title || "New conversation"}
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-stone-500">
            {vehicle || plate ? (
              <>
                {/* the plate shows the registration once we know it, the car name goes next to it */}
                <NumberPlate label={plate || vehicle} />
                {plate && vehicle && <span className="font-medium text-stone-700">{vehicle}</span>}
                {conversation?.vehicle.odometer_km ? (
                  <span>{conversation.vehicle.odometer_km.toLocaleString("en-IN")} km</span>
                ) : null}
              </>
            ) : (
              <span>{conversation ? "Car not set yet" : "Describe the problem and I'll help figure it out"}</span>
            )}
          </div>
        </div>

        <Stepper stage={stage} />

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onOpenLogs}
            className="relative inline-flex items-center gap-1.5 rounded-lg border border-stone-200 bg-white px-2.5 py-1.5 text-sm text-stone-700 transition hover:border-stone-300 hover:bg-stone-50"
            title="See every API call and whether Gemini was used"
          >
            <Activity className="size-4" />
            <span className="hidden xl:inline">API logs</span>
            {aiTrouble && <span className="absolute -right-1 -top-1 size-2.5 rounded-full bg-red-500 ring-2 ring-white" />}
          </button>

          {canDiagnose && (
            <button
              type="button"
              onClick={onDiagnose}
              disabled={busy}
              aria-label="Diagnose now"
              className="inline-flex items-center gap-1.5 rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:border-stone-300 hover:bg-stone-50 disabled:opacity-50"
              title="Skip the remaining questions and diagnose with what you've told me"
            >
              <Stethoscope className="size-4" />
              <span className="hidden sm:inline">Diagnose now</span>
            </button>
          )}

          {canBook && (
            <button
              type="button"
              onClick={onBook}
              aria-label="Book mechanic"
              className="inline-flex items-center gap-1.5 rounded-lg bg-ink-900 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-ink-700"
            >
              <CalendarPlus className="size-4" />
              <span className="hidden sm:inline">Book mechanic</span>
            </button>
          )}
        </div>
      </div>

      {/* compact progress bar where the stepper doesn't fit */}
      <div className="h-0.5 bg-stone-100 lg:hidden">
        <div className="h-full bg-brand-500 transition-all duration-500" style={{ width: `${progress * 100}%` }} />
      </div>
    </header>
  );
}
