// No login in this app. Each browser gets a random id that the backend uses to
// keep conversations separate. It lives in localStorage so history survives reloads.

const STORAGE_KEY = "garagemate.clientId";
let cachedId: string | null = null;

function randomId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  // older browsers / non https
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
    const value = (Math.random() * 16) | 0;
    return (char === "x" ? value : (value & 0x3) | 0x8).toString(16);
  });
}

export function getClientId(): string {
  if (cachedId) return cachedId;

  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) {
      cachedId = saved;
      return saved;
    }
  } catch {
    // private mode or storage disabled, we'll just use an in-memory id
  }

  cachedId = randomId();
  try {
    window.localStorage.setItem(STORAGE_KEY, cachedId);
  } catch {
    // ignore
  }
  return cachedId;
}
