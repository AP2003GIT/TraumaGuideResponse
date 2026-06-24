import type {
  AccountExport,
  AdminDashboard,
  AuthResponse,
  ChatMessage,
  ChatResponse,
  PasswordResetRequestResponse,
  SavedConversation,
  SavedConversationList,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

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

function authHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
  };
}

export async function registerAccount(
  displayName: string,
  email: string,
  password: string,
): Promise<AuthResponse> {
  return authRequest("/api/auth/register", {
    display_name: displayName,
    email,
    password,
  });
}

export async function loginAccount(
  email: string,
  password: string,
): Promise<AuthResponse> {
  return authRequest("/api/auth/login", {
    email,
    password,
  });
}

export async function continueAsDeveloper(): Promise<AuthResponse> {
  const displayName = "Developer";
  const email = "developer@local.dev";
  const password = "developer-password";

  try {
    return await loginAccount(email, password);
  } catch {
    return registerAccount(displayName, email, password);
  }
}

export async function getCurrentUser(
  token: string,
): Promise<AuthResponse["user"]> {
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: authHeaders(token),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as AuthResponse["user"];
}

export async function requestPasswordReset(
  email: string,
): Promise<PasswordResetRequestResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/auth/password-reset/request`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email }),
    },
  );

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as PasswordResetRequestResponse;
}

export async function confirmPasswordReset(
  resetToken: string,
  newPassword: string,
): Promise<AuthResponse> {
  return authRequest("/api/auth/password-reset/confirm", {
    reset_token: resetToken,
    new_password: newPassword,
  });
}

export async function updateAccountProfile(
  token: string,
  displayName: string,
  email: string,
  currentPassword: string,
  newPassword: string,
): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/account/profile`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token),
    },
    body: JSON.stringify({
      display_name: displayName,
      email,
      current_password: currentPassword || null,
      new_password: newPassword || null,
    }),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as AuthResponse;
}

async function authRequest(
  path: string,
  body: Record<string, string>,
): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as AuthResponse;
}

export async function sendChatMessage(
  message: string,
  history: ChatMessage[],
  sessionId: string,
  token: string,
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token),
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
  token: string,
): Promise<SavedConversation | null> {
  const response = await fetch(
    `${API_BASE_URL}/api/conversations/${encodeURIComponent(sessionId)}`,
    {
      headers: authHeaders(token),
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as SavedConversation;
}

export async function getSavedConversations(
  token: string,
): Promise<SavedConversationList> {
  const response = await fetch(`${API_BASE_URL}/api/conversations`, {
    headers: authHeaders(token),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as SavedConversationList;
}

export async function deleteSavedConversation(
  sessionId: string,
  token: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/conversations/${encodeURIComponent(sessionId)}`,
    {
      method: "DELETE",
      headers: authHeaders(token),
    },
  );

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }
}

export async function exportAccountData(
  token: string,
): Promise<AccountExport> {
  const response = await fetch(`${API_BASE_URL}/api/account/export`, {
    headers: authHeaders(token),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as AccountExport;
}

export async function deleteAccountData(token: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/account`, {
    method: "DELETE",
    headers: authHeaders(token),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }
}

export async function getAdminDashboard(
  token: string,
): Promise<AdminDashboard> {
  const response = await fetch(`${API_BASE_URL}/api/admin/dashboard`, {
    headers: authHeaders(token),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response));
  }

  return (await response.json()) as AdminDashboard;
}
