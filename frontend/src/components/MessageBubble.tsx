"use client";

import { AlertTriangle, ArrowRight, CalendarCheck, Info, Loader2, RotateCw, Sparkles, TriangleAlert } from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";

import { aiFailureLabel, formatDate } from "@/lib/format";
import type { Diagnosis } from "@/lib/types";

import AttachmentView from "./AttachmentView";
import type { ChatItem } from "./ChatApp";
import DiagnosisCard from "./DiagnosisCard";
import Logo from "./Logo";
import SourceList from "./SourceList";

interface MessageBubbleProps {
  message: ChatItem;
  showQuickReplies: boolean;
  booked: boolean;
  onQuickReply: (text: string) => void;
  onRetry: (item: ChatItem) => void;
  onBook: (diagnosis: Diagnosis | null) => void;
  onOpenLogs: () => void;
}

function Markdown({ text }: { text: string }) {
  return (
    <div className="chat-markdown text-[14px] leading-relaxed">
      <ReactMarkdown
        components={{
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer" className="underline">
              {children}
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

function time(value: string) {
  return new Date(value).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
}

function UserMessage({ message, onRetry }: { message: ChatItem; onRetry: (item: ChatItem) => void }) {
  return (
    <div className="flex animate-rise flex-col items-end gap-1.5">
      {message.attachments.length > 0 && (
        <div className="flex max-w-[85%] flex-wrap justify-end gap-2">
          {message.attachments.map((attachment) => (
            <AttachmentView key={attachment.id} attachment={attachment} />
          ))}
        </div>
      )}
      {message.content && (
        <div
          className={`max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md px-4 py-2.5 text-[14px] leading-relaxed shadow-sm sm:max-w-[75%] ${
            message.status === "failed" ? "bg-red-50 text-red-900 ring-1 ring-red-200" : "bg-ink-900 text-stone-50"
          }`}
        >
          {message.content}
        </div>
      )}
      {message.status === "sending" && (
        <span className="flex items-center gap-1 text-[11px] text-stone-400">
          <Loader2 className="size-3 animate-spin" /> Sending
        </span>
      )}
      {message.status === "failed" && (
        <span className="flex items-center gap-2 text-xs text-red-600">
          {message.error}
          <button type="button" onClick={() => onRetry(message)} className="inline-flex items-center gap-1 font-medium underline underline-offset-2">
            <RotateCw className="size-3" /> Retry
          </button>
        </span>
      )}
      {!message.status && <span className="pr-1 text-[10px] text-stone-400">{time(message.created_at)}</span>}
    </div>
  );
}

export default function MessageBubble({
  message,
  showQuickReplies,
  booked,
  onQuickReply,
  onRetry,
  onBook,
  onOpenLogs,
}: MessageBubbleProps) {
  if (message.role === "user") return <UserMessage message={message} onRetry={onRetry} />;

  const isDiagnosis = message.kind === "diagnosis" && message.diagnosis;
  // anything the bot said before the diagnosis block (safety warnings, intro line). The block starts with a
  // bold heading line, found that way instead of by the word "Diagnosis" so it works in Hindi too.
  const headingAt = isDiagnosis ? message.content.search(/^\*\*/m) : -1;
  const textBeforeDiagnosis = headingAt > 0 ? message.content.slice(0, headingAt).trim() : "";

  const bubbleStyle =
    message.kind === "rejection"
      ? "bg-stone-50 text-stone-700 ring-stone-200"
      : message.kind === "error"
        ? "bg-red-50 text-red-900 ring-red-200"
        : "bg-white text-ink-800 ring-stone-200/80";

  return (
    <div className="flex animate-rise items-start gap-2.5">
      <Logo className="mt-5 size-8 shrink-0" />

      <div className="min-w-0 max-w-[92%] flex-1 space-y-2 sm:max-w-[82%]">
        <p className="flex items-center gap-2 pl-1 text-[11px] text-stone-500">
          <span className="font-semibold text-ink-900">GarageMate</span>
          <span>{time(message.created_at)}</span>
          {message.used_ai && (
            <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-1.5 py-px text-[10px] font-medium text-violet-700 ring-1 ring-violet-100">
              <Sparkles className="size-2.5" /> Gemini
            </span>
          )}
        </p>

        {isDiagnosis ? (
          <>
            {textBeforeDiagnosis && (
              <div className="rounded-2xl rounded-tl-md bg-white px-4 py-3 text-ink-800 shadow-sm ring-1 ring-stone-200/80">
                <Markdown text={textBeforeDiagnosis} />
              </div>
            )}
            <DiagnosisCard diagnosis={message.diagnosis!} booked={booked} onBook={() => onBook(message.diagnosis)} />
          </>
        ) : (
          <div className={`rounded-2xl rounded-tl-md px-4 py-3 shadow-sm ring-1 ${bubbleStyle}`}>
            {message.kind === "rejection" && (
              <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-stone-500">
                <Info className="size-3.5" /> Outside what I can help with
              </p>
            )}
            {message.kind === "error" && (
              <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-red-700">
                <AlertTriangle className="size-3.5" /> Something went wrong
              </p>
            )}
            <Markdown text={message.content} />

            {message.kind === "booking_confirmed" && message.booking && (
              <Link
                href={`/booking/${message.booking.id}`}
                className="mt-3 flex items-center gap-3 rounded-xl bg-ink-900 px-3.5 py-3 text-sm text-white transition hover:bg-ink-700"
              >
                <span className="grid size-9 place-items-center rounded-lg bg-brand-500 text-ink-950">
                  <CalendarCheck className="size-5" />
                </span>
                <span className="flex-1">
                  <span className="block font-mono font-semibold tracking-wide">{message.booking.reference}</span>
                  <span className="text-xs text-stone-300">
                    {formatDate(message.booking.scheduled_date)}, {message.booking.time_slot_label}
                  </span>
                </span>
                <span className="flex items-center gap-1 text-xs font-medium text-brand-300">
                  View <ArrowRight className="size-3.5" />
                </span>
              </Link>
            )}

            {message.sources && message.sources.length > 0 && (
              <div className="mt-3 border-t border-stone-100 pt-2.5">
                <SourceList sources={message.sources} />
              </div>
            )}

            {message.kind === "booking_prompt" && (
              <button
                type="button"
                onClick={() => onBook(null)}
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-3.5 py-2 text-sm font-semibold text-ink-950 transition hover:bg-brand-400"
              >
                Open booking form <ArrowRight className="size-4" />
              </button>
            )}
          </div>
        )}

        {message.ai_error && (
          <div className="flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-900 ring-1 ring-amber-200">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
            <p className="flex-1">
              Gemini couldn&apos;t help with this one ({aiFailureLabel(message.ai_error)}), so I answered with the
              rule based checks. Everything else keeps working.{" "}
              <button type="button" onClick={onOpenLogs} className="font-semibold underline underline-offset-2">
                See API logs
              </button>
            </p>
          </div>
        )}

        {showQuickReplies && message.quick_replies.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {message.quick_replies.map((reply) => (
              <button
                key={reply}
                type="button"
                onClick={() => onQuickReply(reply)}
                className="rounded-full border border-stone-300 bg-white px-3.5 py-1.5 text-[13px] font-medium text-ink-800 shadow-sm transition hover:-translate-y-px hover:border-brand-400 hover:bg-brand-50 hover:text-brand-800"
              >
                {reply}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
