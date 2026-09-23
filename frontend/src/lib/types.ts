export type Severity = "low" | "medium" | "high" | "critical";

export type Stage = "new" | "gathering" | "diagnosed" | "booked";

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
  created_at: string;
}

export interface Vehicle {
  make: string;
  model: string;
  year: number | null;
  odometer_km: number | null;
  fuel_type: string;
}

export interface Conversation {
  id: string;
  title: string;
  stage: Stage;
  issue_category: string;
  vehicle: Vehicle;
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
}
