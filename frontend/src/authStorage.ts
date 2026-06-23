import type { AuthenticatedUser } from "./types";

export type DisplayMode = "light" | "dark";

const DISPLAY_MODE_KEY = "emotional-support-display-mode";
const AUTH_TOKEN_KEY = "emotional-support-auth-token";
const AUTH_USER_KEY = "emotional-support-auth-user";

export function getSavedDisplayMode(): DisplayMode {
  try {
    const savedMode = localStorage.getItem(DISPLAY_MODE_KEY);
    if (savedMode === "light" || savedMode === "dark") {
      return savedMode;
    }
  } catch {
    // Fall back to the default when browser storage is unavailable.
  }

  return "light";
}

export function saveDisplayMode(displayMode: DisplayMode) {
  try {
    localStorage.setItem(DISPLAY_MODE_KEY, displayMode);
  } catch {
    // The selected mode still applies for the current session.
  }
}

export function getSavedAuth(): {
  token: string | null;
  user: AuthenticatedUser | null;
} {
  const rememberedAuth = readStoredAuth(localStorage);
  if (rememberedAuth.token && rememberedAuth.user) {
    return rememberedAuth;
  }

  return readStoredAuth(sessionStorage);
}

function readStoredAuth(storage: Storage): {
  token: string | null;
  user: AuthenticatedUser | null;
} {
  try {
    const token = storage.getItem(AUTH_TOKEN_KEY);
    const rawUser = storage.getItem(AUTH_USER_KEY);
    if (!token || !rawUser) {
      return { token: null, user: null };
    }

    const parsedUser = JSON.parse(rawUser) as Partial<AuthenticatedUser>;
    if (
      !parsedUser.user_id ||
      !parsedUser.email ||
      !parsedUser.display_name
    ) {
      return { token: null, user: null };
    }

    return {
      token,
      user: {
        user_id: parsedUser.user_id,
        email: parsedUser.email,
        display_name: parsedUser.display_name,
        role: parsedUser.role === "admin" ? "admin" : "user",
      },
    };
  } catch {
    return { token: null, user: null };
  }
}

export function saveAuth(
  token: string,
  user: AuthenticatedUser,
  rememberMe: boolean,
) {
  clearAuth();

  const storage = rememberMe ? localStorage : sessionStorage;

  try {
    storage.setItem(AUTH_TOKEN_KEY, token);
    storage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  } catch {
    // Auth remains available until the page reloads.
  }
}

export function clearAuth() {
  try {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
    sessionStorage.removeItem(AUTH_USER_KEY);
  } catch {
    // Local storage is best effort.
  }
}

export function isAuthRemembered(): boolean {
  try {
    return Boolean(localStorage.getItem(AUTH_TOKEN_KEY));
  } catch {
    return false;
  }
}
