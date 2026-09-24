export type Severity = "low" | "medium" | "high" | "critical";

export type Stage = "new" | "gathering" | "diagnosed" | "booked";

export type Language = "en" | "hi" | "hinglish";

export interface Source {
  title: string;
  url: string;
}

// web research behind a diagnosis: fuel news, recalls, known issues for the model
export interface Research {
  summary?: string;
  sources?: Source[];
  queries?: string[];
  searched_at?: string;
}

// the card text translated when the chat isn't in English
export interface LocalizedDiagnosis {
  language?: Language;
  title?: string;
  summary?: string;
  advice?: string;
  causes?: string[];
  research_summary?: string;
}

export type MessageKind =
  | "text"
  | "question"
  | "diagnosis"
  | "rejection"
  | "booking_prompt"
  | "booking_confirmed"
  | "error";

export interface Service {
  code: string;
  name: string;
  description: string;
  price_min: number;
  price_max: number;
  duration_minutes: number;
}

export interface ProbableCause {
  name: string;
  likelihood: number;
}

export interface Diagnosis {
  id: number;
  conversation_id: string;
  category: string;
  category_label: string;
  title: string;
  summary: string;
  probable_causes: ProbableCause[];
  severity: Severity;
  severity_label: string;
  safe_to_drive: boolean;
  advice: string;
  recommended_service: Service | null;
  estimated_cost_min: number | null;
  estimated_cost_max: number | null;
  source: "rules" | "ai";
  research?: Research;
  localized?: LocalizedDiagnosis;
  created_at: string;
}

export interface Attachment {
  id: string;
  kind: "image" | "audio" | "video";
  mime_type: string;
  size_bytes: number;
  original_name: string;
  url: string;
  created_at: string;
}

export interface BookingSummary {
  id: string;
  reference: string;
  status: BookingStatus;
  service_name: string;
  mechanic_name: string | null;
  scheduled_date: string;
  time_slot: string;
  time_slot_label: string;
}

export interface Message {
  id: number;
  role: "user" | "assistant";
  kind: MessageKind;
  content: string;
  quick_replies: string[];
  action: string;
  attachments: Attachment[];
  diagnosis: Diagnosis | null;
  booking: BookingSummary | null;
  used_ai: boolean;
  ai_error: string;
  sources?: Source[];
  created_at: string;
}

export interface Vehicle {
  make: string;
  model: string;
  year: number | null;
  odometer_km: number | null;
  fuel_type: string;
  // older api versions don't send it
  registration_number?: string;
}

export interface Conversation {
  id: string;
  title: string;
  stage: Stage;
  issue_category: string;
  language?: Language;
  vehicle: Vehicle;
  car_id: number | null;
  latest_diagnosis: { id: number; title: string; severity: Severity } | null;
  last_message: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface ChatResponse {
  conversation: Conversation;
  user_message: Message;
  reply: Message;
}

export interface DiagnosisResponse {
  diagnosis: Diagnosis;
  message: Message | null;
}

export interface Slot {
  value: string;
  label: string;
  remaining: number;
  available: boolean;
}

export type BookingStatus = "confirmed" | "completed" | "cancelled";
export type ServiceMode = "garage" | "doorstep" | "pickup";

export interface Mechanic {
  name: string;
  phone: string;
  speciality: string;
  experience_years: number;
}

export interface Booking {
  id: string;
  reference: string;
  status: BookingStatus;
  status_label: string;
  can_cancel: boolean;
  service: Service;
  mechanic: Mechanic | null;
  customer_name: string;
  phone: string;
  email: string;
  vehicle_make: string;
  vehicle_model: string;
  vehicle_year: number | null;
  registration_number: string;
  service_mode: ServiceMode;
  service_mode_label: string;
  address: string;
  scheduled_date: string;
  time_slot: string;
  time_slot_label: string;
  notes: string;
  conversation_id: string | null;
  diagnosis_id: number | null;
  created_at: string;
}

export interface Car {
  id: number;
  make: string;
  model: string;
  year: number | null;
  fuel_type: string;
  odometer_km: number | null;
  registration_number: string;
  is_primary: boolean;
  label: string;
  created_at: string;
}

export type CarInput = Omit<Car, "id" | "label" | "created_at">;

export interface Profile {
  name: string;
  phone: string;
  email: string;
  city: string;
  cars: Car[];
}

export interface AiCall {
  purpose: string;
  model: string;
  ok: boolean;
  reason: string;
  message: string;
  duration_ms: number;
  custom_key: boolean;
}

export interface RequestLog {
  id: number;
  method: string;
  path: string;
  status_code: number;
  duration_ms: number;
  error: string;
  ai_calls: AiCall[];
  created_at: string;
}

export interface LogsResponse {
  gemini: {
    status: "ok" | "failing" | "unknown" | "not_configured";
    reason: string;
    last_call_at: string | null;
    model: string;
    fallback_model: string;
    using_custom_key: boolean;
  };
  stats: {
    requests: number;
    bot_replies: number;
    handled_by_rules: number;
    ai_calls: number;
    ai_failures: number;
  };
  results: RequestLog[];
}

export interface AiCheckResponse {
  ok: boolean;
  reason: string;
  using_custom_key: boolean;
  duration_ms: number;
}

export interface BookingRequest {
  service: string;
  conversation_id?: string | null;
  diagnosis_id?: number | null;
  customer_name: string;
  phone: string;
  email?: string;
  vehicle_make: string;
  vehicle_model: string;
  vehicle_year?: number | null;
  registration_number?: string;
  service_mode: ServiceMode;
  address?: string;
  scheduled_date: string;
  time_slot: string;
  notes?: string;
  save_details?: boolean;
}
