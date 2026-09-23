"use client";

import { Activity, CalendarCheck, ChevronRight, Plus, Trash2, UserRound, X } from "lucide-react";

import { CategoryIcon } from "@/lib/categories";
import { severityStyles, timeAgo } from "@/lib/format";
import type { Conversation, Profile } from "@/lib/types";

import Logo from "./Logo";

interface SidebarProps {
  conversations: Conversation[];
  loading: boolean;
  activeId: string | null;
  open: boolean;
  profile: Profile | null;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
  onOpenProfile: () => void;
  onOpenLogs: () => void;
}

function groupByDay(conversations: Conversation[]) {
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);

  const groups: { label: string; items: Conversation[] }[] = [
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Earlier", items: [] },
  ];
  for (const item of conversations) {
    const updated = new Date(item.updated_at);
    const index = updated >= startOfToday ? 0 : updated >= startOfYesterday ? 1 : 2;
    groups[index].items.push(item);
  }
  return groups.filter((group) => group.items.length > 0);
}

function StatusBadge({ conversation }: { conversation: Conversation }) {
  if (conversation.stage === "booked") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-sky-400/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-sky-300">
        <CalendarCheck className="size-3" /> Booked
      </span>
    );
  }
  if (conversation.latest_diagnosis) {
    const style = severityStyles[conversation.latest_diagnosis.severity];
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-white/8 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-stone-300">
        <span className={`size-1.5 rounded-full ${style.dot}`} /> Diagnosed
      </span>
    );
  }
  if (conversation.stage === "gathering") {
    return <span className="text-[10px] font-medium uppercase tracking-wide text-stone-500">In progress</span>;
  }
  return null;
}

export default function Sidebar({
  conversations,
  loading,
  activeId,
  open,
  profile,
  onClose,
  onSelect,
  onNewChat,
  onDelete,
  onOpenProfile,
  onOpenLogs,
}: SidebarProps) {
  const confirmDelete = (conversation: Conversation) => {
    if (window.confirm(`Delete "${conversation.title || "this conversation"}"? This can't be undone.`)) {
      onDelete(conversation.id);
    }
  };

  const primaryCar = profile?.cars.find((car) => car.is_primary) ?? profile?.cars[0];
  const initials = (profile?.name || "")
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <>
      {/* dark overlay behind the drawer on mobile */}
      <div
        className={`fixed inset-0 z-30 bg-black/50 backdrop-blur-[1px] transition-opacity md:hidden ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
        onClick={onClose}
        aria-hidden
      />

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[288px] flex-col bg-ink-900 text-stone-100 transition-transform md:static md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Conversation history"
      >
        <div className="flex items-center justify-between px-4 pb-4 pt-5">
          <div className="flex items-center gap-2.5">
            <Logo className="size-9" />
            <div>
              <p className="font-display text-[17px] font-semibold leading-none tracking-tight">GarageMate</p>
              <p className="mt-1 text-[11px] text-stone-400">Your virtual mechanic</p>
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
            className="group flex w-full items-center gap-2 rounded-xl bg-brand-500 px-3.5 py-2.5 text-sm font-semibold text-ink-950 shadow-[0_6px_20px_-8px] shadow-brand-500/60 transition hover:bg-brand-400"
          >
            <Plus className="size-4" /> New conversation
            <ChevronRight className="ml-auto size-4 opacity-60 transition group-hover:translate-x-0.5" />
          </button>
        </div>

        <nav className="dark-scroll mt-4 flex-1 overflow-y-auto px-2 pb-4">
          {loading && [0, 1, 2].map((key) => <div key={key} className="mx-1 mb-1.5 h-[60px] animate-pulse rounded-xl bg-white/5" />)}

          {!loading && conversations.length === 0 && (
            <div className="mx-1 rounded-xl border border-dashed border-white/10 px-3 py-4 text-sm text-stone-400">
              No conversations yet. Your chats and diagnoses will show up here.
            </div>
          )}

          {groupByDay(conversations).map((group) => (
            <div key={group.label} className="mb-3">
              <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-500">{group.label}</p>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const active = item.id === activeId;
                  const vehicle = [item.vehicle.make, item.vehicle.model].filter(Boolean).join(" ");
                  return (
                    <div
                      key={item.id}
                      className={`group relative rounded-xl transition ${active ? "bg-white/10 ring-1 ring-white/10" : "hover:bg-white/[0.05]"}`}
                    >
                      <button type="button" onClick={() => onSelect(item.id)} className="flex w-full gap-3 px-2.5 py-2.5 pr-9 text-left">
                        <span
                          className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg ${
                            active ? "bg-brand-500 text-ink-950" : "bg-white/[0.07] text-stone-300"
                          }`}
                        >
                          <CategoryIcon category={item.issue_category} className="size-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[13px] font-medium">{item.title || "New conversation"}</span>
                          <span className="mt-0.5 block truncate text-xs text-stone-400">
                            {item.latest_diagnosis?.title || vehicle || item.last_message || "No messages yet"}
                          </span>
                          <span className="mt-1.5 flex items-center gap-2">
                            <StatusBadge conversation={item} />
                            <span className="text-[10px] text-stone-500">{timeAgo(item.updated_at)}</span>
                          </span>
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => confirmDelete(item)}
                        className="absolute right-2 top-2.5 rounded-md p-1 text-stone-500 transition hover:bg-white/10 hover:text-red-300 md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"
                        aria-label={`Delete ${item.title || "conversation"}`}
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="space-y-2 border-t border-white/[0.07] p-3">
          <button
            type="button"
            onClick={onOpenProfile}
            className="flex w-full items-center gap-3 rounded-xl bg-white/[0.04] px-3 py-2.5 text-left transition hover:bg-white/[0.08]"
          >
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-stone-200 to-stone-400 text-xs font-bold text-ink-900">
              {initials || <UserRound className="size-4" />}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{profile?.name || "Set up your garage"}</span>
              <span className="block truncate text-xs text-stone-400">
                {primaryCar ? primaryCar.label : "Save your car for faster help"}
              </span>
            </span>
            <ChevronRight className="size-4 text-stone-500" />
          </button>
          <div className="flex items-center justify-between px-1 text-[11px] text-stone-500">
            <span className="flex items-center gap-1.5">
              <span className="size-1.5 rounded-full bg-emerald-400" /> Workshop open Mon-Sat, 9-6
            </span>
            <button type="button" onClick={onOpenLogs} className="flex items-center gap-1 hover:text-stone-300">
              <Activity className="size-3" /> API logs
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
