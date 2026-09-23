"use client";

import { AlertCircle, X } from "lucide-react";
import { useEffect } from "react";

export default function Toast({ message, onDismiss }: { message: string | null; onDismiss: () => void }) {
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(onDismiss, 5000);
    return () => window.clearTimeout(timer);
  }, [message, onDismiss]);

  if (!message) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-24 z-50 flex justify-center px-4">
      <div
        role="alert"
        className="pointer-events-auto flex max-w-md items-start gap-2 rounded-lg bg-stone-900 px-4 py-3 text-sm text-white shadow-lg"
      >
        <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-400" />
        <p className="flex-1">{message}</p>
        <button type="button" onClick={onDismiss} className="text-stone-400 hover:text-white" aria-label="Dismiss">
          <X className="size-4" />
        </button>
      </div>
    </div>
  );
}
