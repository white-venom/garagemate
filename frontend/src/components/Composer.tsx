"use client";

import { AlertCircle, FileAudio, Film, Loader2, Mic, Paperclip, SendHorizontal, Square, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";
import { api, errorMessage } from "@/lib/api";
import { formatFileSize } from "@/lib/format";
import type { Attachment } from "@/lib/types";

// same limits as the backend (chat/uploads.py)
const MB = 1024 * 1024;
const SIZE_LIMITS = { image: 8 * MB, audio: 10 * MB, video: 15 * MB };
const MAX_FILES = 4;

type Kind = keyof typeof SIZE_LIMITS;

interface PendingUpload {
  key: string;
  file: File;
  kind: Kind;
  previewUrl: string | null;
  progress: number;
  status: "uploading" | "done" | "error";
  attachment?: Attachment;
  error?: string;
}

interface ComposerProps {
  conversationId: string | null;
  disabled: boolean;
  onSend: (text: string, attachments: Attachment[]) => void;
  onError: (message: string) => void;
}

function kindOf(file: File): Kind | null {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("audio/")) return "audio";
  if (file.type.startsWith("video/")) return "video";
  return null;
}

function formatSeconds(total: number) {
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export default function Composer({ conversationId, disabled, onSend, onError }: ComposerProps) {
  const [text, setText] = useState("");
  const [uploads, setUploads] = useState<PendingUpload[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const uploadCounter = useRef(0);

  const updateUpload = (key: string, patch: Partial<PendingUpload>) => {
    setUploads((previous) => previous.map((item) => (item.key === key ? { ...item, ...patch } : item)));
  };

  const startUpload = (item: PendingUpload) => {
    api
      .uploadFile(item.file, conversationId, (progress) => updateUpload(item.key, { progress }))
      .then((attachment) => updateUpload(item.key, { status: "done", progress: 100, attachment }))
      .catch((error) => updateUpload(item.key, { status: "error", error: errorMessage(error) }));
  };

  const addFiles = (files: File[]) => {
    const room = MAX_FILES - uploads.length;
    if (files.length > room) onError(`You can attach up to ${MAX_FILES} files to one message.`);

    const accepted: PendingUpload[] = [];
    for (const file of files.slice(0, Math.max(room, 0))) {
      const kind = kindOf(file);
      if (!kind) {
        onError(`${file.name}: only photos, audio and video files are supported.`);
        continue;
      }
      if (file.size > SIZE_LIMITS[kind]) {
        onError(`${file.name} is too big. ${kind[0].toUpperCase() + kind.slice(1)} files can be up to ${SIZE_LIMITS[kind] / MB} MB.`);
        continue;
      }
      accepted.push({
        key: `upload-${++uploadCounter.current}`,
        file,
        kind,
        previewUrl: kind === "image" ? URL.createObjectURL(file) : null,
        progress: 0,
        status: "uploading",
      });
    }
    if (accepted.length === 0) return;
    setUploads((previous) => [...previous, ...accepted]);
    accepted.forEach(startUpload);
  };

  const recorder = useVoiceRecorder((file) => addFiles([file]));

  const removeUpload = (key: string) => {
    const item = uploads.find((upload) => upload.key === key);
    if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl);
    setUploads((previous) => previous.filter((upload) => upload.key !== key));
  };

  // grow the textarea with its content, up to ~6 lines
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
  }, [text]);

  const uploading = uploads.some((item) => item.status === "uploading");
  const ready = uploads.flatMap((item) => (item.status === "done" && item.attachment ? [item.attachment] : []));
  const canSend = !disabled && !uploading && recorder.state === "idle" && (text.trim().length > 0 || ready.length > 0);

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim(), ready);
    uploads.forEach((item) => item.previewUrl && URL.revokeObjectURL(item.previewUrl));
    setUploads([]);
    setText("");
    textareaRef.current?.focus();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  const handlePaste = (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(event.clipboardData.files);
    if (files.length > 0) {
      event.preventDefault();
      addFiles(files);
    }
  };

  const recording = recorder.state === "recording";

  return (
    <div className="border-t border-stone-200 bg-white px-3 pb-3 pt-2 sm:px-6">
      <div className="mx-auto max-w-3xl">
        {uploads.length > 0 && (
          <ul className="mb-2 flex flex-wrap gap-2">
            {uploads.map((item) => (
              <li
                key={item.key}
                className={`relative flex w-52 items-center gap-2 overflow-hidden rounded-xl border p-2 text-xs ${
                  item.status === "error" ? "border-red-200 bg-red-50" : "border-stone-200 bg-stone-50"
                }`}
              >
                {item.previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element -- local blob preview
                  <img src={item.previewUrl} alt="" className="size-10 shrink-0 rounded-lg object-cover" />
                ) : (
                  <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-stone-200 text-stone-600">
                    {item.kind === "video" ? <Film className="size-5" /> : <FileAudio className="size-5" />}
                  </span>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-stone-800">{item.file.name}</p>
                  <p className={item.status === "error" ? "truncate text-red-600" : "text-stone-500"} title={item.error}>
                    {item.status === "error"
                      ? item.error
                      : item.status === "uploading"
                        ? `Uploading ${item.progress}%`
                        : formatFileSize(item.file.size)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => removeUpload(item.key)}
                  className="rounded p-0.5 text-stone-400 hover:bg-stone-200 hover:text-stone-700"
                  aria-label={`Remove ${item.file.name}`}
                >
                  <X className="size-4" />
                </button>
                {item.status === "uploading" && (
                  <span className="absolute inset-x-0 bottom-0 h-0.5 bg-amber-500 transition-all" style={{ width: `${item.progress}%` }} />
                )}
              </li>
            ))}
          </ul>
        )}

        {recorder.error && (
          <p className="mb-2 flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
            <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
            <span className="flex-1">{recorder.error}</span>
            <button type="button" onClick={recorder.clearError} aria-label="Dismiss" className="hover:text-red-900">
              <X className="size-3.5" />
            </button>
          </p>
        )}

        <div className="flex items-end gap-1.5 rounded-2xl border border-stone-300 bg-stone-50 p-1.5 focus-within:border-amber-400 focus-within:ring-2 focus-within:ring-amber-200">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,audio/*,video/*"
            multiple
            hidden
            onChange={(event) => {
              addFiles(Array.from(event.target.files ?? []));
              event.target.value = "";
            }}
          />

          {recording || recorder.state === "processing" ? (
            <div className="flex min-h-10 flex-1 items-center gap-3 px-2 text-sm">
              {recording ? (
                <>
                  <span className="size-2.5 animate-pulse rounded-full bg-red-500" />
                  <span className="tabular-nums text-stone-700">
                    Recording {formatSeconds(recorder.seconds)} / {formatSeconds(recorder.maxSeconds)}
                  </span>
                  <button type="button" onClick={recorder.cancel} className="ml-auto text-stone-500 hover:text-stone-800">
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={recorder.stop}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-red-500 px-3 py-1.5 font-medium text-white hover:bg-red-600"
                  >
                    <Square className="size-3.5 fill-current" /> Stop
                  </button>
                </>
              ) : (
                <span className="flex items-center gap-2 text-stone-500">
                  <Loader2 className="size-4 animate-spin" /> Preparing voice note...
                </span>
              )}
            </div>
          ) : (
            <>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploads.length >= MAX_FILES}
                className="grid size-10 shrink-0 place-items-center rounded-xl text-stone-500 transition hover:bg-stone-200 hover:text-stone-800 disabled:opacity-40"
                aria-label="Attach photo, audio or video"
                title="Attach photo, audio or video"
              >
                <Paperclip className="size-5" />
              </button>
              <button
                type="button"
                onClick={recorder.start}
                disabled={uploads.length >= MAX_FILES}
                className="grid size-10 shrink-0 place-items-center rounded-xl text-stone-500 transition hover:bg-stone-200 hover:text-stone-800 disabled:opacity-40"
                aria-label="Record the sound"
                title="Record the sound your car is making"
              >
                <Mic className="size-5" />
              </button>
              <textarea
                ref={textareaRef}
                value={text}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                rows={1}
                maxLength={2000}
                placeholder="Describe the problem, e.g. grinding noise when I brake"
                className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-stone-900 outline-none placeholder:text-stone-400"
                aria-label="Message"
              />
            </>
          )}

          <button
            type="button"
            onClick={submit}
            disabled={!canSend}
            className="grid size-10 shrink-0 place-items-center rounded-xl bg-amber-500 text-stone-900 transition hover:bg-amber-400 disabled:bg-stone-200 disabled:text-stone-400"
            aria-label="Send message"
          >
            {disabled ? <Loader2 className="size-5 animate-spin" /> : <SendHorizontal className="size-5" />}
          </button>
        </div>

        <p className="mt-1.5 hidden text-center text-[11px] text-stone-400 sm:block">
          Enter to send, Shift + Enter for a new line. Photos up to 8 MB, audio 10 MB, video 15 MB.
        </p>
      </div>
    </div>
  );
}
