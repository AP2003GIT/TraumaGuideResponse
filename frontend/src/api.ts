import type { ChatMessage, ChatResponse } from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

interface ErrorBody {
  detail?: unknown;
}

export async function sendChatMessage(
  message: string,
  history: ChatMessage[],
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      history,
    }),
  });

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}.`;

    try {
      const body = (await response.json()) as ErrorBody;
      if (typeof body.detail === "string") {
        errorMessage = body.detail;
      } else if (body.detail) {
        errorMessage = JSON.stringify(body.detail);
      }
    } catch {
      // Keep the default message when the response is not JSON.
    }

    throw new Error(errorMessage);
  }

  return (await response.json()) as ChatResponse;
}
