import type {
  ChatMessage,
  ChatResponse,
  SavedConversation,
  SavedConversationList,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

interface ErrorBody {
  detail?: unknown;
}

async function getErrorMessage(response: Response): Promise<string> {
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

  return errorMessage;
}

export async function sendChatMessage(
  message: string,
  history: ChatMessage[],
  sessionId: string,
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      history,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as ChatResponse;
}

export async function getSavedConversation(
  sessionId: string,
): Promise<SavedConversation | null> {
  const response = await fetch(
    `${API_BASE_URL}/api/conversations/${encodeURIComponent(sessionId)}`,
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as SavedConversation;
}

export async function getSavedConversations(): Promise<SavedConversationList> {
  const response = await fetch(`${API_BASE_URL}/api/conversations`);

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as SavedConversationList;
}

export async function deleteSavedConversation(
  sessionId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/conversations/${encodeURIComponent(sessionId)}`,
    {
      method: "DELETE",
    },
  );

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }
}
