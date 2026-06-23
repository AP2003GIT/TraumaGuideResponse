import type {
  ChatMessage,
  RiskLevel,
  SavedChatMessage,
} from "./types";

export interface DisplayMessage extends ChatMessage {
  id: string;
  riskLevel?: RiskLevel;
  createdAt: string;
  status?: "failed";
}

const SAVED_SESSION_KEY = "emotional-support-session-id";

export function createId(): string {
  return crypto.randomUUID();
}

export function saveSessionId(sessionId: string) {
  try {
    localStorage.setItem(SAVED_SESSION_KEY, sessionId);
  } catch {
    // The session still works for the current page load.
  }
}

export function getSavedSessionId(): string {
  try {
    const existingSessionId = localStorage.getItem(SAVED_SESSION_KEY);
    if (existingSessionId) {
      return existingSessionId;
    }

    const sessionId = createId();
    saveSessionId(sessionId);
    return sessionId;
  } catch {
    return createId();
  }
}

export function toDisplayMessage(
  message: SavedChatMessage,
): DisplayMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    riskLevel: message.risk_level ?? undefined,
    createdAt: message.created_at,
  };
}

export function formatSavedDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatMessageTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
