"use client";

import { CheckCircle2, KeyRound, Loader2, RefreshCw, Sparkles, Terminal, X, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { aiFailureLabel, timeAgo } from "@/lib/format";
import { clearCustomGeminiKey, getCustomGeminiKey, maskKey, setCustomGeminiKey } from "@/lib/geminiKey";
import type { AiCheckResponse, LogsResponse, RequestLog } from "@/lib/types";

const POLL_MS = 4000;

const methodStyles: Record<string, string> = {
  GET: "bg-sky-400/15 text-sky-300",
  POST: "bg-emerald-400/15 text-emerald-300",
  DELETE: "bg-red-400/15 text-red-300",
};

function statusColor(status: number) {
  if (status >= 500) return "text-red-400";
  if (status >= 400) return "text-amber-300";
  return "text-emerald-400";
}

function formatDuration(ms: number) {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function GeminiStatus({ data }: { data: LogsResponse["gemini"] }) {
  const failing = data.status === "failing" || data.status === "not_configured";
  const label =
    data.status === "ok"
      ? "Working"
      : data.status === "failing"
        ? `Unavailable, ${aiFailureLabel(data.reason)}`
        : data.status === "not_configured"
          ? "No API key on the server"
          : "Not called yet";

  return (
    <div>
      <p className="flex items-center gap-2 text-sm font-semibold text-white">
        <span className="relative flex size-2.5">
          {data.status === "ok" && <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400 opacity-60" />}
          <span className={`relative size-2.5 rounded-full ${data.status === "ok" ? "bg-emerald-400" : failing ? "bg-red-500" : "bg-stone-500"}`} />
        </span>
        Gemini: {label}
      </p>
      <p className="mt-1.5 font-mono text-[11px] text-stone-400">
        {data.model} → fallback {data.fallback_model}
        {data.last_call_at && ` · last call ${timeAgo(data.last_call_at)}`}
      </p>
      {failing && (
        <p className="mt-3 rounded-lg bg-amber-400/10 px-3 py-2.5 text-xs leading-relaxed text-amber-100 ring-1 ring-amber-400/20">
          The app still works. Follow-up questions, diagnosis, off-topic checks and bookings are all rule based. Only
          photo / audio / video analysis and open questions need Gemini, and those fall back to a plain reply until
          it&apos;s back. The free quota resets daily.
        </p>
      )}
    </div>
  );
}

function OwnKeyForm({ onSaved }: { onSaved: () => void }) {
  const [savedKey, setSavedKey] = useState(() => getCustomGeminiKey());
  const [input, setInput] = useState("");
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<AiCheckResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const test = async () => {
    setChecking(true);
    setError(null);
    try {
      const check = await api.checkGemini();
      setResult(check);
      // a rejected key is useless, don't keep sending it
      if (!check.ok && check.reason === "invalid_key" && check.using_custom_key) {
        clearCustomGeminiKey();
        setSavedKey("");
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setChecking(false);
      onSaved();
    }
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (input.trim().length < 20) {
      setError("That doesn't look like a Gemini API key.");
      return;
    }
    setCustomGeminiKey(input);
    setSavedKey(input.trim());
    setInput("");
    await test();
  };

  const remove = () => {
    clearCustomGeminiKey();
    setSavedKey("");
    setResult(null);
    onSaved();
  };

  return (
    <div className="mt-3 rounded-xl border border-white/10 bg-white/[0.03] p-3.5">
      <p className="flex items-center gap-1.5 text-sm font-medium text-white">
        <KeyRound className="size-4 text-brand-400" /> Use your own Gemini key
      </p>
      <p className="mt-1 text-xs leading-relaxed text-stone-400">
        Free at{" "}
        <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" className="text-stone-200 underline">
          aistudio.google.com/apikey
        </a>
        . It stays in this browser and only goes along with your own requests. The server never saves it.
      </p>

      {savedKey ? (
        <div className="mt-3 flex items-center justify-between gap-2 text-sm">
          <span className="font-mono text-stone-300">{maskKey(savedKey)}</span>
          <div className="flex gap-2">
            <button type="button" onClick={test} disabled={checking} className="rounded-md border border-white/15 px-2.5 py-1 text-xs text-stone-200 hover:bg-white/10">
              {checking ? "Testing..." : "Test"}
            </button>
            <button type="button" onClick={remove} className="rounded-md border border-red-400/30 px-2.5 py-1 text-xs text-red-300 hover:bg-red-500/10">
              Remove
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={save} className="mt-3 flex gap-2">
          <input
            type="password"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Paste API key"
            autoComplete="off"
            className="min-w-0 flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white outline-none placeholder:text-stone-500 focus:border-brand-400"
          />
          <button type="submit" disabled={checking} className="rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-50">
            {checking ? <Loader2 className="size-4 animate-spin" /> : "Save & test"}
          </button>
        </form>
      )}

      {result && (
        <p className={`mt-2 flex items-center gap-1.5 text-xs ${result.ok ? "text-emerald-300" : "text-red-300"}`}>
          {result.ok ? <CheckCircle2 className="size-3.5" /> : <XCircle className="size-3.5" />}
          {result.ok ? `Gemini answered in ${formatDuration(result.duration_ms)}, you're all set.` : `Didn't work: ${aiFailureLabel(result.reason)}.`}
        </p>
      )}
      {error && <p className="mt-2 text-xs text-red-300">{error}</p>}
    </div>
  );
}

function LogRow({ log }: { log: RequestLog }) {
  return (
    <li className="px-4 py-3 transition hover:bg-white/[0.02]">
      <div className="flex items-center gap-2 font-mono text-xs">
        <span className={`w-12 rounded px-1.5 py-0.5 text-center text-[10px] font-semibold ${methodStyles[log.method] ?? "bg-white/10 text-stone-300"}`}>
          {log.method}
        </span>
        <span className="min-w-0 flex-1 truncate text-stone-200" title={log.path}>
          {log.path}
        </span>
        <span className={`font-semibold ${statusColor(log.status_code)}`}>{log.status_code}</span>
        <span className="w-12 text-right text-stone-500">{formatDuration(log.duration_ms)}</span>
      </div>
      <p className="mt-1 pl-14 font-mono text-[10px] text-stone-600">{new Date(log.created_at).toLocaleTimeString()}</p>

      {log.error && <p className="mt-1 pl-14 text-xs text-amber-300/90">↳ {log.error}</p>}

      {log.ai_calls.map((call, index) => (
        <p
          key={index}
          className={`ml-14 mt-1.5 flex items-start gap-1.5 rounded-md px-2 py-1 text-[11px] ${
            call.ok ? "bg-violet-400/10 text-violet-200" : "bg-red-500/10 text-red-300"
          }`}
        >
          <Sparkles className="mt-0.5 size-3 shrink-0" />
          <span className="min-w-0 flex-1">
            {call.purpose} · <span className="font-mono">{call.model}</span>
            {call.custom_key && " · your key"}
            {call.ok ? ` · ${formatDuration(call.duration_ms)}` : ` · ${aiFailureLabel(call.reason)}`}
          </span>
          {call.ok ? <CheckCircle2 className="mt-0.5 size-3 shrink-0" /> : <XCircle className="mt-0.5 size-3 shrink-0" />}
        </p>
      ))}
    </li>
  );
}

export default function ApiLogsPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [data, setData] = useState<LogsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.getLogs());
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    // first fetch right away, then keep polling while the panel is open
    const first = window.setTimeout(() => void load(), 0);
    const timer = window.setInterval(() => void load(), POLL_MS);
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
      window.removeEventListener("keydown", handleKey);
    };
  }, [open, load, onClose]);

  if (!open) return null;

  const gemini = data?.gemini;
  const showKeyForm = gemini && (gemini.status === "failing" || gemini.status === "not_configured" || gemini.using_custom_key);

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[1px]" onClick={onClose} aria-hidden />
      <aside
        className="fixed inset-y-0 right-0 z-50 flex w-full animate-rise flex-col bg-ink-950 text-stone-200 shadow-2xl sm:w-[460px]"
        aria-label="API logs"
      >
        <header className="flex items-center gap-3 border-b border-white/10 px-4 py-3.5">
          <span className="grid size-8 place-items-center rounded-lg bg-white/[0.06]">
            <Terminal className="size-4 text-brand-400" />
          </span>
          <div className="flex-1">
            <h2 className="font-display text-sm font-semibold text-white">API logs</h2>
            <p className="text-[11px] text-stone-500">Calls from this browser, live</p>
          </div>
          <button type="button" onClick={() => void load()} className="rounded-md p-1.5 text-stone-400 hover:bg-white/10 hover:text-white" aria-label="Refresh">
            <RefreshCw className="size-4" />
          </button>
          <button type="button" onClick={onClose} className="rounded-md p-1.5 text-stone-400 hover:bg-white/10 hover:text-white" aria-label="Close API logs">
            <X className="size-5" />
          </button>
        </header>

        <div className="dark-scroll flex-1 overflow-y-auto">
          {!data && !error && (
            <p className="flex items-center gap-2 p-4 text-sm text-stone-400">
              <Loader2 className="size-4 animate-spin" /> Loading...
            </p>
          )}
          {error && <p className="m-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}

          {data && (
            <>
              <section className="border-b border-white/10 p-4">
                <GeminiStatus data={data.gemini} />
                {showKeyForm && <OwnKeyForm onSaved={() => void load()} />}
              </section>

              <section className="grid grid-cols-4 gap-2 border-b border-white/10 p-4 text-center">
                {[
                  { label: "API calls", value: data.stats.requests },
                  { label: "Bot replies", value: data.stats.bot_replies },
                  { label: "Rules only", value: data.stats.handled_by_rules },
                  {
                    label: "Gemini calls",
                    value: data.stats.ai_calls,
                    note: data.stats.ai_failures ? `${data.stats.ai_failures} failed` : "",
                  },
                ].map((stat) => (
                  <div key={stat.label} className="rounded-xl bg-white/[0.04] px-1 py-2.5 ring-1 ring-white/[0.06]">
                    <p className="font-display text-xl font-semibold tabular-nums text-white">{stat.value}</p>
                    <p className="text-[10px] uppercase tracking-wide text-stone-500">{stat.label}</p>
                    {stat.note && <p className="text-[10px] text-red-400">{stat.note}</p>}
                  </div>
                ))}
              </section>

              {data.results.length === 0 ? (
                <p className="p-4 text-sm text-stone-500">No API calls yet. Send a message and they&apos;ll show up here.</p>
              ) : (
                <ul className="divide-y divide-white/[0.06]">
                  {data.results.map((log) => (
                    <LogRow key={log.id} log={log} />
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </aside>
    </>
  );
}
