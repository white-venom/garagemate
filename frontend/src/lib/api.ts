import { getClientId } from "./clientId";
import { getCustomGeminiKey } from "./geminiKey";
import type {
  AiCheckResponse,
  Attachment,
  Booking,
  BookingRequest,
  Car,
  CarInput,
  ChatResponse,
  Conversation,
  ConversationDetail,
  DiagnosisResponse,
  LogsResponse,
  Profile,
  Service,
  Slot,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type FieldErrors = Record<string, string[] | string>;

export class ApiError extends Error {
  status: number;
  code: string;
  fields?: FieldErrors;

  constructor(message: string, status: number, code: string, fields?: FieldErrors) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string; fields?: FieldErrors };
}

function toApiError(status: number, body: ErrorBody | null): ApiError {
  const error = body?.error;
  if (status === 429) {
    return new ApiError(error?.message || "Slow down a little, too many requests.", status, "throttled");
  }
  return new ApiError(
    error?.message || `Something went wrong (${status}). Please try again.`,
    status,
    error?.code || "error",
    error?.fields,
  );
}

async function request<T>(path: string, options: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...init } = options;
  const headers = new Headers(init.headers);
  headers.set("X-Client-Id", getClientId());
  headers.set("Accept", "application/json");
  // only set when our Gemini key is failing and the visitor added their own
  const geminiKey = getCustomGeminiKey();
  if (geminiKey) headers.set("X-Gemini-Key", geminiKey);
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    init.body = JSON.stringify(json);
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError("Can't reach the server. Check your internet connection and try again.", 0, "network_error");
  }

  if (response.status === 204) return undefined as T;

  const body = await response.json().catch(() => null);
  if (!response.ok) throw toApiError(response.status, body);
  return body as T;
}

// fetch() can't report upload progress, so uploads use XHR
function uploadFile(file: File, conversationId: string | null, onProgress?: (percent: number) => void) {
  return new Promise<Attachment>((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    if (conversationId) form.append("conversation_id", conversationId);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/upload/`);
    xhr.setRequestHeader("X-Client-Id", getClientId());
    xhr.setRequestHeader("Accept", "application/json");

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      let body = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // not json, handled below
      }
      if (xhr.status >= 200 && xhr.status < 300 && body) resolve(body as Attachment);
      else reject(toApiError(xhr.status, body));
    };
    xhr.onerror = () => reject(new ApiError("Upload failed. Check your connection and try again.", 0, "network_error"));
    xhr.send(form);
  });
}

export const api = {
  sendMessage: (body: { conversation_id?: string | null; message: string; attachment_ids?: string[] }) =>
    request<ChatResponse>("/api/chat/", { method: "POST", json: body }),

  uploadFile,

  requestDiagnosis: (conversationId: string) =>
    request<DiagnosisResponse>("/api/diagnosis/", { method: "POST", json: { conversation_id: conversationId } }),

  listConversations: () => request<{ results: Conversation[] }>("/api/conversations/"),

  getConversation: (id: string) => request<ConversationDetail>(`/api/conversations/${id}/`),

  deleteConversation: (id: string) => request<void>(`/api/conversations/${id}/`, { method: "DELETE" }),

  listServices: () => request<{ results: Service[] }>("/api/services/"),

  getSlots: (date: string) => request<{ date: string; slots: Slot[] }>(`/api/booking/slots/?date=${date}`),

  createBooking: (body: BookingRequest) => request<Booking>("/api/booking/", { method: "POST", json: body }),

  getBooking: (id: string) => request<Booking>(`/api/booking/${id}/`),

  cancelBooking: (id: string) => request<Booking>(`/api/booking/${id}/cancel/`, { method: "POST" }),

  getProfile: () => request<Profile>("/api/profile/"),

  updateProfile: (body: Partial<Omit<Profile, "cars">>) => request<Profile>("/api/profile/", { method: "PUT", json: body }),

  addCar: (body: Partial<CarInput>) => request<Car>("/api/profile/cars/", { method: "POST", json: body }),

  updateCar: (id: number, body: Partial<CarInput>) => request<Car>(`/api/profile/cars/${id}/`, { method: "PATCH", json: body }),

  deleteCar: (id: number) => request<void>(`/api/profile/cars/${id}/`, { method: "DELETE" }),

  getLogs: () => request<LogsResponse>("/api/logs/"),

  checkGemini: () => request<AiCheckResponse>("/api/ai/check/", { method: "POST" }),
};

export function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "Something unexpected happened. Please try again.";
}
