"use client";

import { Camera, Gauge, Mic, ShieldCheck, Wrench } from "lucide-react";
import { useEffect, useRef } from "react";

import type { Diagnosis, Stage } from "@/lib/types";

import type { ChatItem } from "./ChatApp";
import MessageBubble from "./MessageBubble";

const EXAMPLES = [
  "My brakes make a squeaking noise",
  "Car won't start in the morning, just clicks",
  "AC is blowing warm air",
  "Check engine light came on",
  "Engine is overheating in traffic",
  "White smoke from the exhaust",
];

interface MessageListProps {
  messages: ChatItem[];
  loading: boolean;
  typing: boolean;
  stage: Stage;
  onQuickReply: (text: string) => void;
  onRetry: (item: ChatItem) => void;
  onBook: (diagnosis: Diagnosis | null) => void;
}

function Welcome({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center px-4 py-10 text-center sm:py-16">
      <span className="grid size-14 place-items-center rounded-2xl bg-amber-500 text-stone-900 shadow-sm">
        <Wrench className="size-7" />
      </span>
      <h2 className="mt-5 text-2xl font-semibold text-stone-900 sm:text-3xl">What&apos;s up with your car?</h2>
      <p className="mt-2 max-w-md text-sm text-stone-600 sm:text-base">
        Tell me the symptoms like you would at the workshop counter. I&apos;ll ask a few questions, give you a
        diagnosis and can book a mechanic for you.
      </p>

      <div className="mt-6 grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => onPick(example)}
            className="rounded-xl border border-stone-200 bg-white px-4 py-3 text-left text-sm text-stone-700 shadow-sm transition hover:border-amber-400 hover:bg-amber-50"
          >
            {example}
          </button>
        ))}
      </div>

      <div className="mt-8 grid w-full grid-cols-1 gap-3 text-left text-xs text-stone-500 sm:grid-cols-3">
        <p className="flex items-start gap-2">
          <Camera className="mt-0.5 size-4 shrink-0 text-stone-400" /> Send photos of leaks, tyres or warning lights
        </p>
        <p className="flex items-start gap-2">
          <Mic className="mt-0.5 size-4 shrink-0 text-stone-400" /> Record the noise your car is making
        </p>
        <p className="flex items-start gap-2">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-stone-400" /> Get told straight if it&apos;s unsafe to drive
        </p>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-end gap-2" aria-live="polite" aria-label="Mechanic is typing">
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-stone-900 text-amber-400">
        <Gauge className="size-4" />
      </span>
      <div className="flex gap-1 rounded-2xl rounded-bl-sm bg-white px-4 py-3 shadow-sm ring-1 ring-stone-200">
        <span className="typing-dot size-2 rounded-full bg-stone-400" />
        <span className="typing-dot size-2 rounded-full bg-stone-400" />
        <span className="typing-dot size-2 rounded-full bg-stone-400" />
      </div>
    </div>
  );
}

export default function MessageList({ messages, loading, typing, stage, onQuickReply, onRetry, onBook }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, typing]);

  if (loading) {
    return (
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-6">
        {[0, 1, 2].map((key) => (
          <div key={key} className={`h-16 animate-pulse rounded-2xl bg-stone-200 ${key % 2 ? "ml-auto w-1/2" : "w-2/3"}`} />
        ))}
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 overflow-y-auto">
        <Welcome onPick={onQuickReply} />
      </div>
    );
  }

  // quick replies only make sense on the very last bot message
  const lastIndex = messages.length - 1;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-4 px-3 py-6 sm:px-6" role="log" aria-live="polite">
        {messages.map((item, index) => (
          <MessageBubble
            key={item.localId ?? item.id}
            message={item}
            showQuickReplies={index === lastIndex && !typing}
            booked={stage === "booked"}
            onQuickReply={onQuickReply}
            onRetry={onRetry}
            onBook={onBook}
          />
        ))}
        {typing && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
