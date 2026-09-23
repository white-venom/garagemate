import { createElement } from "react";

import {
  ArrowUpDown,
  BatteryWarning,
  CircleDot,
  ClipboardCheck,
  CloudFog,
  Cog,
  Disc3,
  Droplets,
  Gauge,
  MessageSquareText,
  Snowflake,
  Thermometer,
  Zap,
  type LucideIcon,
} from "lucide-react";

// matches the issue keys in backend/diagnosis/knowledge_base.py
export const categoryIcons: Record<string, LucideIcon> = {
  brakes: Disc3,
  starting: BatteryWarning,
  engine: Gauge,
  overheating: Thermometer,
  transmission: Cog,
  suspension: ArrowUpDown,
  tyres: CircleDot,
  ac: Snowflake,
  electrical: Zap,
  exhaust: CloudFog,
  leaks: Droplets,
  routine: ClipboardCheck,
};

export function iconFor(category: string | null | undefined): LucideIcon {
  return (category && categoryIcons[category]) || MessageSquareText;
}

export const SYMPTOM_SHORTCUTS = [
  { category: "brakes", title: "Brakes squeaking", hint: "Squeal, grinding, soft pedal", prompt: "My brakes make a squeaking noise" },
  { category: "starting", title: "Won't start", hint: "Clicking, slow crank, dead battery", prompt: "Car won't start in the morning, just clicks" },
  { category: "ac", title: "AC not cooling", hint: "Warm air, weak flow, bad smell", prompt: "AC is blowing warm air" },
  { category: "engine", title: "Check engine light", hint: "Warning light, rough idle, low power", prompt: "Check engine light came on" },
  { category: "overheating", title: "Overheating", hint: "Gauge in the red, steam, coolant", prompt: "Engine is overheating in traffic" },
  { category: "exhaust", title: "Smoke from exhaust", hint: "White, blue or black smoke", prompt: "White smoke from the exhaust" },
];

// wrapper so components don't pick an icon component during render (react-hooks/static-components)
export function CategoryIcon({ category, className }: { category: string | null | undefined; className?: string }) {
  return createElement(iconFor(category), { className });
}
