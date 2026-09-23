import type { Severity, Stage } from "./types";

const rupees = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function formatRupees(amount: number | null | undefined) {
  return amount == null ? "" : rupees.format(amount);
}

export function formatPriceRange(min: number | null, max: number | null) {
  if (min == null || max == null) return "Quote after inspection";
  return `${formatRupees(min)} - ${formatRupees(max)}`;
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(value: string) {
  // yyyy-mm-dd from the api, parse as a local date so it doesn't shift a day
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function timeAgo(value: string) {
  const seconds = Math.round((Date.now() - new Date(value).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(value).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function toDateInputValue(date: Date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export const severityStyles: Record<Severity, { label: string; badge: string; bar: string; dot: string }> = {
  low: { label: "Low", badge: "bg-emerald-50 text-emerald-700 ring-emerald-200", bar: "bg-emerald-500", dot: "bg-emerald-500" },
  medium: { label: "Medium", badge: "bg-amber-50 text-amber-800 ring-amber-200", bar: "bg-amber-500", dot: "bg-amber-500" },
  high: { label: "High", badge: "bg-orange-50 text-orange-700 ring-orange-200", bar: "bg-orange-500", dot: "bg-orange-500" },
  critical: { label: "Critical", badge: "bg-red-50 text-red-700 ring-red-200", bar: "bg-red-600", dot: "bg-red-600" },
};

export const aiFailureLabels: Record<string, string> = {
  quota: "the free tier quota is used up",
  overloaded: "Gemini is overloaded right now",
  timeout: "Gemini took too long to answer",
  invalid_key: "the API key was rejected",
  model_not_found: "the model isn't available",
  not_configured: "no API key is set on the server",
  empty: "Gemini returned an empty answer",
  bad_response: "Gemini's answer couldn't be read",
  error: "the request failed",
};

export function aiFailureLabel(reason: string) {
  return aiFailureLabels[reason] ?? aiFailureLabels.error;
}

export const stageLabels: Record<Stage, string> = {
  new: "New",
  gathering: "Collecting details",
  diagnosed: "Diagnosed",
  booked: "Mechanic booked",
};
