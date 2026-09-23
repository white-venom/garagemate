"use client";

import { CalendarCheck, MessageSquarePlus, Trash2, Wrench, X } from "lucide-react";

import { severityStyles, timeAgo } from "@/lib/format";
import type { Conversation } from "@/lib/types";

interface SidebarProps {
  conversations: Conversation[];
  loading: boolean;
  activeId: string | null;
  open: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
}

function StatusBadge({ conversation }: { conversation: Conversation }) {
  if (conversation.stage === "booked") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/15 px-2 py-0.5 text-[11px] font-medium text-sky-300">
        <CalendarCheck className="size-3" /> Booked
      </span>
    );
  }
  if (conversation.latest_diagnosis) {
    const style = severityStyles[conversation.latest_diagnosis.severity];
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-medium text-stone-200">
        <span className={`size-1.5 rounded-full ${style.dot}`} /> Diagnosed
      </span>
    );
  }
  return null;
}

export default function Sidebar({
  conversations,
  loading,
  activeId,
  open,
  onClose,
  onSelect,
  onNewChat,
  onDelete,
}: SidebarProps) {
  const confirmDelete = (conversation: Conversation) => {
    if (window.confirm(`Delete "${conversation.title || "this conversation"}"? This can't be undone.`)) {
      onDelete(conversation.id);
    }
  };

  return (
    <>
      {/* dark overlay behind the drawer on mobile */}
      <div
        className={`fixed inset-0 z-30 bg-black/40 transition-opacity md:hidden ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
        onClick={onClose}
        aria-hidden
      />

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col bg-stone-900 text-stone-100 transition-transform md:static md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Conversation history"
      >
        <div className="flex items-center justify-between px-4 pb-3 pt-4">
          <div className="flex items-center gap-2">
            <span className="grid size-8 place-items-center rounded-lg bg-amber-500 text-stone-900">
              <Wrench className="size-4" />
            </span>
            <div>
              <p className="text-sm font-semibold leading-tight">GarageMate</p>
              <p className="text-xs text-stone-400">Virtual mechanic</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-stone-400 hover:bg-white/10 hover:text-white md:hidden"
            aria-label="Close menu"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="px-3">
          <button
            type="button"
            onClick={onNewChat}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-3 py-2 text-sm font-semibold text-stone-900 transition hover:bg-amber-400"
          >
            <MessageSquarePlus className="size-4" /> New conversation
          </button>
        </div>

        <p className="px-4 pb-2 pt-5 text-xs font-medium uppercase tracking-wide text-stone-500">History</p>

        <nav className="flex-1 space-y-1 overflow-y-auto px-2 pb-4">
          {loading &&
            [0, 1, 2].map((key) => <div key={key} className="mx-1 h-14 animate-pulse rounded-lg bg-white/5" />)}

          {!loading && conversations.length === 0 && (
            <p className="px-3 py-2 text-sm text-stone-400">
              No conversations yet. Your chats and diagnoses will show up here.
            </p>
          )}

          {conversations.map((item) => {
            const active = item.id === activeId;
            const vehicle = [item.vehicle.make, item.vehicle.model].filter(Boolean).join(" ");
            return (
              <div
                key={item.id}
                className={`group relative rounded-lg transition ${active ? "bg-white/10" : "hover:bg-white/5"}`}
              >
                <button type="button" onClick={() => onSelect(item.id)} className="w-full px-3 py-2.5 pr-9 text-left">
                  <p className="truncate text-sm font-medium">{item.title || "New conversation"}</p>
                  <p className="mt-0.5 truncate text-xs text-stone-400">
                    {item.latest_diagnosis?.title || vehicle || item.last_message || "No messages yet"}
                  </p>
                  <div className="mt-1.5 flex items-center gap-2">
                    <StatusBadge conversation={item} />
                    <span className="text-[11px] text-stone-500">{timeAgo(item.updated_at)}</span>
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => confirmDelete(item)}
                  className="absolute right-2 top-2.5 rounded p-1 text-stone-500 opacity-100 transition hover:bg-white/10 hover:text-red-300 md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"
                  aria-label={`Delete ${item.title || "conversation"}`}
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
            );
          })}
        </nav>

        <p className="border-t border-white/10 px-4 py-3 text-xs text-stone-500">
          Chats are saved for this browser only.
        </p>
      </aside>
    </>
  );
}
