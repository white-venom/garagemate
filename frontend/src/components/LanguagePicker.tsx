"use client";

import { ChevronDown, Languages } from "lucide-react";

import type { Language } from "@/lib/types";

const OPTIONS: { value: Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिंदी" },
  { value: "hinglish", label: "Hinglish" },
];

// replies come in this language, the bot understands all three either way
export default function LanguagePicker({ value, onChange }: { value: Language; onChange: (language: Language) => void }) {
  const current = OPTIONS.find((option) => option.value === value) ?? OPTIONS[0];
  return (
    <label className="relative inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-full border border-stone-200 bg-white px-2 py-0.5 text-[11px] text-stone-500 transition hover:border-stone-300 hover:text-ink-800">
      <Languages className="size-3" />
      <span>
        Reply in <span className="font-semibold text-ink-800">{current.label}</span>
      </span>
      <ChevronDown className="size-3" />
      {/* the real select sits on top, invisible, so the phone's own picker opens */}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as Language)}
        aria-label="Reply language"
        className="absolute inset-0 cursor-pointer opacity-0"
      >
        {OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
