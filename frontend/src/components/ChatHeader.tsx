"use client";

import { CalendarPlus, Car, Menu, Stethoscope } from "lucide-react";

import { stageLabels } from "@/lib/format";
import type { Conversation } from "@/lib/types";

interface ChatHeaderProps {
  conversation: Conversation | null;
  busy: boolean;
  onOpenMenu: () => void;
  onDiagnose: () => void;
  onBook: () => void;
}

export default function ChatHeader({ conversation, busy, onOpenMenu, onDiagnose, onBook }: ChatHeaderProps) {
  const vehicle = conversation
    ? [conversation.vehicle.year, conversation.vehicle.make, conversation.vehicle.model].filter(Boolean).join(" ")
    : "";
  const canDiagnose = conversation?.stage === "gathering" && Boolean(conversation.issue_category);
  const canBook = conversation?.stage === "diagnosed" || conversation?.stage === "booked";

  return (
    <header className="flex items-center gap-3 border-b border-stone-200 bg-white px-4 py-3">
      <button
        type="button"
        onClick={onOpenMenu}
        className="-ml-1 rounded-md p-1.5 text-stone-600 hover:bg-stone-100 md:hidden"
        aria-label="Open conversation history"
      >
        <Menu className="size-5" />
      </button>

      <div className="min-w-0 flex-1">
        <h1 className="truncate text-sm font-semibold text-stone-900 sm:text-base">
          {conversation?.title || "New conversation"}
        </h1>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-stone-500">
          {conversation && <span>{stageLabels[conversation.stage]}</span>}
          {vehicle && (
            <span className="inline-flex items-center gap-1">
              <Car className="size-3.5" /> {vehicle}
              {conversation?.vehicle.odometer_km ? ` · ${conversation.vehicle.odometer_km.toLocaleString("en-IN")} km` : ""}
            </span>
          )}
          {!conversation && <span>Describe the problem and I&apos;ll help figure it out</span>}
        </div>
      </div>

      {canDiagnose && (
        <button
          type="button"
          onClick={onDiagnose}
          disabled={busy}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 transition hover:bg-stone-50 disabled:opacity-50"
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
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-stone-900 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-stone-700"
        >
          <CalendarPlus className="size-4" />
          <span className="hidden sm:inline">Book mechanic</span>
        </button>
      )}
    </header>
  );
}
