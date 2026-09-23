// A visitor's own Gemini key, only used when ours has run out of quota.
// It stays in this browser and goes to the backend in the X-Gemini-Key header,
// the server never saves it.

const STORAGE_KEY = "garagemate.geminiKey";

export function getCustomGeminiKey(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function setCustomGeminiKey(key: string) {
  try {
    window.localStorage.setItem(STORAGE_KEY, key.trim());
  } catch {
    // storage blocked, nothing we can do
  }
}

export function clearCustomGeminiKey() {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function maskKey(key: string) {
  return key.length > 10 ? `${key.slice(0, 4)}••••${key.slice(-4)}` : "••••";
}
