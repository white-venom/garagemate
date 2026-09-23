"use client";

import { ArrowRight, Camera, Car, Mic, ShieldCheck } from "lucide-react";
import { useEffect, useRef } from "react";

import { CategoryIcon, SYMPTOM_SHORTCUTS } from "@/lib/categories";
import type { Diagnosis, Profile, Stage } from "@/lib/types";

import type { ChatItem } from "./ChatApp";
import { NumberPlate } from "./ChatHeader";
import Logo from "./Logo";
import MessageBubble from "./MessageBubble";

interface MessageListProps {
  messages: ChatItem[];
  loading: boolean;
  typing: boolean;
  stage: Stage;
  profile: Profile | null;
  onQuickReply: (text: string) => void;
  onRetry: (item: ChatItem) => void;
  onBook: (diagnosis: Diagnosis | null) => void;
  onOpenLogs: () => void;
  onOpenProfile: () => void;
}

const HOW_IT_WORKS = [
  { title: "Describe it", text: "Type it, send a photo or record the noise." },
  { title: "Answer a few questions", text: "Usually 2-4 taps, like at the service counter." },
  { title: "Get a diagnosis & book", text: "Likely cause, cost range, and a mechanic slot." },
];

function Welcome({ profile, onPick, onOpenProfile }: { profile: Profile | null; onPick: (text: string) => void; onOpenProfile: () => void }) {
  const firstName = profile?.name.split(" ")[0];
  const car = profile?.cars.find((item) => item.is_primary) ?? profile?.cars[0];

  return (
    <div className="mx-auto flex max-w-3xl flex-col px-4 py-8 sm:px-6 sm:py-14">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-brand-600">
        <span className="h-px w-6 bg-brand-500" /> Virtual workshop
      </div>
      <h2 className="mt-3 font-display text-[32px] font-semibold leading-[1.05] tracking-tight text-ink-900 sm:text-5xl">
        {firstName ? (
          <>
            Hi {firstName},<br />
            what&apos;s up with {car ? `your ${car.model}` : "your car"}?
          </>
        ) : (
          <>
            Tell me what your
            <br />
            car is doing.
          </>
        )}
      </h2>
      <p className="mt-4 max-w-lg text-[15px] leading-relaxed text-stone-600">
        Describe it like you would at the service counter. I&apos;ll ask a couple of questions, tell you what&apos;s most
        likely wrong and how urgent it is, and book a mechanic if you want one.
      </p>

      {car ? (
        <div className="mt-5 flex flex-wrap items-center gap-2 text-sm text-stone-600">
          <Car className="size-4 text-stone-400" /> Talking about <NumberPlate label={car.label} />
          <button type="button" onClick={onOpenProfile} className="text-xs font-medium text-brand-700 underline-offset-2 hover:underline">
            change
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={onOpenProfile}
          className="mt-5 flex w-full items-center gap-3 rounded-2xl border border-dashed border-stone-300 bg-white/60 px-4 py-3 text-left text-sm transition hover:border-brand-300 hover:bg-white sm:w-auto"
        >
          <span className="grid size-9 place-items-center rounded-xl bg-brand-50 text-brand-600">
            <Car className="size-4" />
          </span>
          <span>
            <span className="block font-medium text-ink-900">Add your car for faster help</span>
            <span className="text-xs text-stone-500">I&apos;ll remember it, so &quot;my car&quot; is all you need to say</span>
          </span>
          <ArrowRight className="ml-auto size-4 text-stone-400" />
        </button>
      )}

      <p className="mt-9 text-xs font-semibold uppercase tracking-[0.12em] text-stone-400">Common problems</p>
      <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {SYMPTOM_SHORTCUTS.map((item) => (
            <button
              key={item.title}
              type="button"
              onClick={() => onPick(item.prompt)}
              className="group flex items-start gap-3 rounded-2xl border border-stone-200/80 bg-white p-3.5 text-left shadow-[0_1px_2px_rgb(0_0_0/0.04)] transition hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md"
            >
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-ink-900 text-brand-400 transition group-hover:bg-brand-500 group-hover:text-ink-950">
                <CategoryIcon category={item.category} className="size-5" />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-ink-900">{item.title}</span>
                <span className="block text-xs text-stone-500">{item.hint}</span>
              </span>
            </button>
        ))}
      </div>

      <div className="mt-9 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {HOW_IT_WORKS.map((step, index) => (
          <div key={step.title} className="flex gap-3">
            <span className="font-display text-2xl font-semibold leading-none text-stone-300">0{index + 1}</span>
            <div>
              <p className="text-sm font-semibold text-ink-900">{step.title}</p>
              <p className="text-xs leading-relaxed text-stone-500">{step.text}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-xs text-stone-500">
        <span className="flex items-center gap-1.5">
          <Camera className="size-3.5" /> Photos of leaks, tyres, warning lights
        </span>
        <span className="flex items-center gap-1.5">
          <Mic className="size-3.5" /> Record the noise it makes
        </span>
        <span className="flex items-center gap-1.5">
          <ShieldCheck className="size-3.5" /> Straight answer if it&apos;s unsafe to drive
        </span>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex animate-rise items-end gap-2.5" aria-live="polite" aria-label="Mechanic is typing">
      <Logo className="size-8 shrink-0" />
      <div className="flex items-center gap-2 rounded-2xl rounded-bl-md bg-white px-4 py-3 shadow-sm ring-1 ring-stone-200/80">
        <span className="flex gap-1">
          <span className="typing-dot size-1.5 rounded-full bg-stone-500" />
          <span className="typing-dot size-1.5 rounded-full bg-stone-500" />
          <span className="typing-dot size-1.5 rounded-full bg-stone-500" />
        </span>
        <span className="text-xs text-stone-400">checking</span>
      </div>
    </div>
  );
}

export default function MessageList({
  messages,
  loading,
  typing,
  stage,
  profile,
  onQuickReply,
  onRetry,
  onBook,
  onOpenLogs,
  onOpenProfile,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, typing]);

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-3xl flex-1 space-y-4 overflow-y-auto px-4 py-6">
        {[0, 1, 2].map((key) => (
          <div key={key} className={`h-16 animate-pulse rounded-2xl bg-stone-200/70 ${key % 2 ? "ml-auto w-1/2" : "w-2/3"}`} />
        ))}
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto">
        <Welcome profile={profile} onPick={onQuickReply} onOpenProfile={onOpenProfile} />
      </div>
    );
  }

  // quick replies only make sense on the very last bot message
  const lastIndex = messages.length - 1;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-5 px-3 py-6 sm:px-6" role="log" aria-live="polite">
        {messages.map((item, index) => (
          <MessageBubble
            key={item.localId ?? item.id}
            message={item}
            showQuickReplies={index === lastIndex && !typing}
            booked={stage === "booked"}
            onQuickReply={onQuickReply}
            onRetry={onRetry}
            onBook={onBook}
            onOpenLogs={onOpenLogs}
          />
        ))}
        {typing && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
