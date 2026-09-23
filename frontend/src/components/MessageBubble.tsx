"use client";

import { AlertTriangle, CalendarCheck, Gauge, Info, Loader2, RotateCw, Sparkles } from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";

import { formatDate } from "@/lib/format";
import type { Diagnosis } from "@/lib/types";

import AttachmentView from "./AttachmentView";
import type { ChatItem } from "./ChatApp";
import DiagnosisCard from "./DiagnosisCard";

interface MessageBubbleProps {
  message: ChatItem;
  showQuickReplies: boolean;
  booked: boolean;
  onQuickReply: (text: string) => void;
  onRetry: (item: ChatItem) => void;
  onBook: (diagnosis: Diagnosis | null) => void;
}

function Markdown({ text }: { text: string }) {
  return (
    <div className="chat-markdown text-sm leading-relaxed">
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

function UserMessage({ message, onRetry }: { message: ChatItem; onRetry: (item: ChatItem) => void }) {
  return (
    <div className="flex flex-col items-end gap-1">
      {message.attachments.length > 0 && (
        <div className="flex max-w-[85%] flex-wrap justify-end gap-2">
          {message.attachments.map((attachment) => (
            <AttachmentView key={attachment.id} attachment={attachment} />
          ))}
        </div>
      )}
      {message.content && (
        <div
          className={`max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm px-4 py-2.5 text-sm shadow-sm sm:max-w-[75%] ${
            message.status === "failed" ? "bg-red-50 text-red-900 ring-1 ring-red-200" : "bg-stone-900 text-white"
          }`}
        >
          {message.content}
        </div>
      )}
      {message.status === "sending" && (
        <span className="flex items-center gap-1 text-xs text-stone-400">
          <Loader2 className="size-3 animate-spin" /> Sending
        </span>
      )}
      {message.status === "failed" && (
        <span className="flex items-center gap-2 text-xs text-red-600">
          {message.error}
          <button
            type="button"
            onClick={() => onRetry(message)}
            className="inline-flex items-center gap-1 font-medium underline underline-offset-2"
          >
            <RotateCw className="size-3" /> Retry
          </button>
        </span>
      )}
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
}: MessageBubbleProps) {
  if (message.role === "user") return <UserMessage message={message} onRetry={onRetry} />;

  const isDiagnosis = message.kind === "diagnosis" && message.diagnosis;
  // anything the bot said before the diagnosis block (safety warnings, intro line)
  const textBeforeDiagnosis = isDiagnosis ? message.content.split("**Diagnosis:")[0].trim() : "";

  const bubbleStyle =
    message.kind === "rejection"
      ? "bg-stone-50 text-stone-700 ring-stone-200"
      : message.kind === "error"
        ? "bg-red-50 text-red-900 ring-red-200"
        : "bg-white text-stone-800 ring-stone-200";

  return (
    <div className="flex items-start gap-2">
      <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-stone-900 text-amber-400">
        <Gauge className="size-4" />
      </span>

      <div className="min-w-0 max-w-[92%] flex-1 space-y-2 sm:max-w-[80%]">
        {isDiagnosis ? (
          <>
            {textBeforeDiagnosis && (
              <div className="rounded-2xl rounded-tl-sm bg-white px-4 py-3 text-stone-800 shadow-sm ring-1 ring-stone-200">
                <Markdown text={textBeforeDiagnosis} />
              </div>
            )}
            <DiagnosisCard diagnosis={message.diagnosis!} booked={booked} onBook={() => onBook(message.diagnosis)} />
          </>
        ) : (
          <div className={`rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm ring-1 ${bubbleStyle}`}>
            {message.kind === "rejection" && (
              <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-stone-500">
                <Info className="size-3.5" /> Outside what I can help with
              </p>
            )}
            {message.kind === "error" && (
              <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-red-700">
                <AlertTriangle className="size-3.5" /> Something went wrong
              </p>
            )}
            <Markdown text={message.content} />

            {message.kind === "booking_confirmed" && message.booking && (
              <Link
                href={`/booking/${message.booking.id}`}
                className="mt-3 flex items-center gap-3 rounded-xl bg-sky-50 px-3 py-2.5 text-sm text-sky-900 ring-1 ring-sky-200 transition hover:bg-sky-100"
              >
                <CalendarCheck className="size-5 shrink-0" />
                <span className="flex-1">
                  <span className="block font-semibold">{message.booking.reference}</span>
                  <span className="text-xs">
                    {formatDate(message.booking.scheduled_date)}, {message.booking.time_slot_label}
                  </span>
                </span>
                <span className="text-xs font-medium underline">View booking</span>
              </Link>
            )}

            {message.kind === "booking_prompt" && (
              <button
                type="button"
                onClick={() => onBook(null)}
                className="mt-3 rounded-lg bg-amber-500 px-3 py-1.5 text-sm font-semibold text-stone-900 hover:bg-amber-400"
              >
                Open booking form
              </button>
            )}
          </div>
        )}

        {message.used_ai && (
          <p className="flex items-center gap-1 pl-1 text-[11px] text-stone-400">
            <Sparkles className="size-3" /> Gemini helped with this reply
          </p>
        )}

        {showQuickReplies && message.quick_replies.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {message.quick_replies.map((reply) => (
              <button
                key={reply}
                type="button"
                onClick={() => onQuickReply(reply)}
                className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1.5 text-sm text-amber-900 transition hover:bg-amber-100"
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
