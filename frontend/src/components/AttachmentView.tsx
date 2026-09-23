import { FileAudio } from "lucide-react";

import type { Attachment } from "@/lib/types";

export default function AttachmentView({ attachment }: { attachment: Attachment }) {
  if (attachment.kind === "image") {
    return (
      <a href={attachment.url} target="_blank" rel="noreferrer" className="block overflow-hidden rounded-xl ring-1 ring-stone-200">
        {/* eslint-disable-next-line @next/next/no-img-element -- user uploads live on the api domain */}
        <img src={attachment.url} alt={attachment.original_name || "Uploaded photo"} className="max-h-56 max-w-[16rem] object-cover" />
      </a>
    );
  }

  if (attachment.kind === "video") {
    return <video src={attachment.url} controls preload="metadata" className="max-h-64 max-w-[18rem] rounded-xl bg-black" />;
  }

  return (
    <div className="flex w-72 max-w-full flex-col gap-2 rounded-xl bg-white p-3 shadow-sm ring-1 ring-stone-200">
      <span className="flex items-center gap-2 text-xs text-stone-500">
        <FileAudio className="size-4" /> {attachment.original_name || "Voice note"}
      </span>
      <audio src={attachment.url} controls preload="metadata" className="h-9 w-full" />
    </div>
  );
}
