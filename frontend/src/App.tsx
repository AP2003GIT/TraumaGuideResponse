import {
  FormEvent,
  KeyboardEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  deleteAccountData,
  deleteSavedConversation,
  exportAccountData,
  getSavedConversation,
  getSavedConversations,
  continueAsDeveloper,
  loginAccount,
  registerAccount,
  sendChatMessage,
} from "./api";
import type {
  AuthenticatedUser,
  ChatMessage,
  Role,
  RiskLevel,
  SavedChatMessage,
  SavedConversationSummary,
} from "./types";

interface DisplayMessage extends ChatMessage {
  id: string;
  riskLevel?: RiskLevel;
  createdAt: string;
  status?: "failed";
}

type DisplayMode = "light" | "dark";
type AuthMode = "login" | "register";
type SettingsTab = "general" | "account" | "privacy" | "safety";

const starterPrompts = [
  "I feel overwhelmed and need a grounding exercise.",
  "Help me understand why stress affects my sleep.",
  "How can I communicate a boundary calmly?",
];

const SAVED_SESSION_KEY = "emotional-support-session-id";
const DISPLAY_MODE_KEY = "emotional-support-display-mode";
const AUTH_TOKEN_KEY = "emotional-support-auth-token";
const AUTH_USER_KEY = "emotional-support-auth-user";
const IS_DEV_LOGIN_ENABLED =
  import.meta.env.VITE_ENABLE_DEV_LOGIN === "true" ||
  (import.meta.env.DEV &&
    import.meta.env.VITE_ENABLE_DEV_LOGIN !== "false");

function createId(): string {
  return crypto.randomUUID();
}

function saveSessionId(sessionId: string) {
  try {
    localStorage.setItem(SAVED_SESSION_KEY, sessionId);
  } catch {
    // The session still works for the current page load.
  }
}

function getSavedSessionId(): string {
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

function getSavedDisplayMode(): DisplayMode {
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

function getSavedAuth(): {
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

    return {
      token,
      user: JSON.parse(rawUser) as AuthenticatedUser,
    };
  } catch {
    return { token: null, user: null };
  }
}

function saveAuth(
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

function clearAuth() {
  try {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
    sessionStorage.removeItem(AUTH_USER_KEY);
  } catch {
    // Local storage is best effort.
  }
}

function toDisplayMessage(message: SavedChatMessage): DisplayMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    riskLevel: message.risk_level ?? undefined,
    createdAt: message.created_at,
  };
}

function formatSavedDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatMessageTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function normalizeAssistantContent(content: string): string {
  return content
    .replace(/\r\n?/g, "\n")
    .replace(/([^\n])\s+(\d+\.\s+)/g, "$1\n$2")
    .replace(/([^\n])\s+([-*]\s+)/g, "$1\n$2");
}

function renderInlineMarkdown(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }

    return part;
  });
}

type ContentBlock =
  | {
      kind: "paragraph";
      text: string;
    }
  | {
      kind: "ordered-list";
      items: string[];
    }
  | {
      kind: "unordered-list";
      items: string[];
    };

function parseAssistantContent(content: string): ContentBlock[] {
  const lines = normalizeAssistantContent(content).split("\n");
  const blocks: ContentBlock[] = [];
  let paragraph: string[] = [];
  let orderedItems: string[] = [];
  let unorderedItems: string[] = [];

  function flushParagraph() {
    if (paragraph.length > 0) {
      blocks.push({
        kind: "paragraph",
        text: paragraph.join(" "),
      });
      paragraph = [];
    }
  }

  function flushOrderedItems() {
    if (orderedItems.length > 0) {
      blocks.push({
        kind: "ordered-list",
        items: orderedItems,
      });
      orderedItems = [];
    }
  }

  function flushUnorderedItems() {
    if (unorderedItems.length > 0) {
      blocks.push({
        kind: "unordered-list",
        items: unorderedItems,
      });
      unorderedItems = [];
    }
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      flushParagraph();
      flushOrderedItems();
      flushUnorderedItems();
      continue;
    }

    const orderedMatch = line.match(/^\d+\.\s+(.+)$/);
    if (orderedMatch) {
      flushParagraph();
      flushUnorderedItems();
      orderedItems.push(orderedMatch[1]);
      continue;
    }

    const unorderedMatch = line.match(/^[-*]\s+(.+)$/);
    if (unorderedMatch) {
      flushParagraph();
      flushOrderedItems();
      unorderedItems.push(unorderedMatch[1]);
      continue;
    }

    flushOrderedItems();
    flushUnorderedItems();
    paragraph.push(line);
  }

  flushParagraph();
  flushOrderedItems();
  flushUnorderedItems();

  return blocks.length > 0
    ? blocks
    : [
        {
          kind: "paragraph",
          text: content,
        },
      ];
}

function MessageContent({
  content,
  role,
}: {
  content: string;
  role: Role;
}) {
  if (role === "user") {
    return (
      <div className="message-content plain">
        <p>{content}</p>
      </div>
    );
  }

  const blocks = parseAssistantContent(content);

  return (
    <div className="message-content formatted">
      {blocks.map((block, index) => {
        if (block.kind === "ordered-list") {
          return (
            <ol key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>
                  {renderInlineMarkdown(item)}
                </li>
              ))}
            </ol>
          );
        }

        if (block.kind === "unordered-list") {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>
                  {renderInlineMarkdown(item)}
                </li>
              ))}
            </ul>
          );
        }

        return <p key={index}>{renderInlineMarkdown(block.text)}</p>;
      })}
    </div>
  );
}

function AuthPanel({
  mode,
  onModeChange,
  onSubmit,
  onDevLogin,
  isSubmitting,
  error,
}: {
  mode: AuthMode;
  onModeChange: (mode: AuthMode) => void;
  onSubmit: (
    mode: AuthMode,
    displayName: string,
    email: string,
    password: string,
    rememberMe: boolean,
  ) => Promise<void>;
  onDevLogin: (rememberMe: boolean) => Promise<void>;
  isSubmitting: boolean;
  error: string | null;
}) {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSubmit(mode, displayName, email, password, rememberMe);
  }

  return (
    <main className="app-shell auth-shell">
      <section className="auth-card">
        <div>
          <p className="eyebrow">Safety-aware AI demo</p>
          <h1>Emotional Support Guide</h1>
          <p className="subtitle">
            Sign in to keep saved chats private to your account.
          </p>
        </div>

        <div className="segmented-control auth-toggle" role="group">
          <button
            type="button"
            className={mode === "login" ? "active" : undefined}
            onClick={() => onModeChange("login")}
          >
            Log in
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : undefined}
            onClick={() => onModeChange("register")}
          >
            Sign up
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {mode === "register" && (
            <label>
              Name
              <input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                minLength={1}
                maxLength={80}
                required
              />
            </label>
          )}

          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>

          <label>
            Password
            <span className="password-field">
              <input
                type={isPasswordVisible ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={8}
                required
              />
              <button
                className="password-toggle"
                type="button"
                onClick={() =>
                  setIsPasswordVisible((current) => !current)
                }
              >
                {isPasswordVisible ? "Hide" : "Show"}
              </button>
            </span>
            <span className="auth-hint">
              Use at least 8 characters for local testing.
            </span>
          </label>

          <label className="remember-me-control">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(event) => setRememberMe(event.target.checked)}
            />
            <span>Remember me on this device</span>
          </label>

          {error && (
            <div className="error-banner auth-error" role="alert">
              {error}
            </div>
          )}

          <button
            className="primary-button"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? "Working..."
              : mode === "register"
                ? "Create account"
                : "Log in"}
          </button>
        </form>

        {IS_DEV_LOGIN_ENABLED && (
          <div className="dev-login-panel">
            <p>Development only</p>
            <button
              className="secondary-button dev-login-button"
              type="button"
              onClick={() => void onDevLogin(rememberMe)}
              disabled={isSubmitting}
            >
              Continue as developer
            </button>
          </div>
        )}
      </section>
    </main>
  );
}

export default function App() {
  const savedAuth = getSavedAuth();
  const [sessionId, setSessionId] = useState(getSavedSessionId);
  const [displayMode, setDisplayMode] =
    useState<DisplayMode>(getSavedDisplayMode);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [authToken, setAuthToken] = useState<string | null>(
    savedAuth.token,
  );
  const [currentUser, setCurrentUser] =
    useState<AuthenticatedUser | null>(savedAuth.user);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isSavedChatsOpen, setIsSavedChatsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("general");
  const [savedChatSearch, setSavedChatSearch] = useState("");
  const [savedChats, setSavedChats] = useState<
    SavedConversationSummary[]
  >([]);
  const [savedChatsLimit, setSavedChatsLimit] = useState(10);
  const [isLoadingSavedChats, setIsLoadingSavedChats] =
    useState(false);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const history = useMemo<ChatMessage[]>(
    () =>
      messages.map(({ role, content }) => ({
        role,
        content,
      })),
    [messages],
  );

  const hasCrisisRisk = messages.some(
    (message) =>
      message.role === "assistant" &&
      (message.riskLevel === "high" ||
        message.riskLevel === "immediate"),
  );

  const filteredSavedChats = useMemo(
    () =>
      savedChats.filter((chat) => {
        const query = savedChatSearch.trim().toLowerCase();
        if (!query) {
          return true;
        }

        return (
          chat.title.toLowerCase().includes(query) ||
          chat.last_message_preview.toLowerCase().includes(query)
        );
      }),
    [savedChatSearch, savedChats],
  );

  useEffect(() => {
    document.documentElement.dataset.theme = displayMode;
    document.documentElement.style.colorScheme = displayMode;

    try {
      localStorage.setItem(DISPLAY_MODE_KEY, displayMode);
    } catch {
      // The selected mode still applies for the current session.
    }
  }, [displayMode]);

  useEffect(() => {
    if (isSavedChatsOpen && authToken) {
      void refreshSavedChats();
    }
  }, [isSavedChatsOpen, authToken]);

  useEffect(() => {
    if (authToken) {
      void refreshSavedChats(false);
    }
  }, [authToken]);

  useEffect(() => {
    if (!authToken) {
      return;
    }

    const token = authToken;
    let isCancelled = false;

    async function loadSavedConversation() {
      try {
        const savedConversation = await getSavedConversation(
          sessionId,
          token,
        );

        if (!isCancelled && savedConversation) {
          setMessages(
            savedConversation.messages.map(toDisplayMessage),
          );
        }
      } catch {
        if (!isCancelled) {
          setError(
            "Saved chat could not be loaded. You can still start a new conversation.",
          );
        }
      }
    }

    void loadSavedConversation();

    return () => {
      isCancelled = true;
    };
  }, [authToken, sessionId]);

  async function handleAuthSubmit(
    mode: AuthMode,
    displayName: string,
    email: string,
    password: string,
    rememberMe: boolean,
  ) {
    setIsAuthenticating(true);
    setAuthError(null);

    try {
      const response =
        mode === "register"
          ? await registerAccount(displayName, email, password)
          : await loginAccount(email, password);

      saveAuth(response.access_token, response.user, rememberMe);
      setAuthToken(response.access_token);
      setCurrentUser(response.user);
      setMessages([]);
      setError(null);
    } catch (caughtError) {
      setAuthError(
        caughtError instanceof Error
          ? caughtError.message
          : "Authentication failed.",
      );
    } finally {
      setIsAuthenticating(false);
    }
  }

  async function handleDevLogin(rememberMe: boolean) {
    setIsAuthenticating(true);
    setAuthError(null);

    try {
      const response = await continueAsDeveloper();

      saveAuth(response.access_token, response.user, rememberMe);
      setAuthToken(response.access_token);
      setCurrentUser(response.user);
      setMessages([]);
      setError(null);
    } catch (caughtError) {
      setAuthError(
        caughtError instanceof Error
          ? caughtError.message
          : "Developer login failed.",
      );
    } finally {
      setIsAuthenticating(false);
    }
  }

  async function refreshSavedChats(showError = true) {
    if (!authToken) {
      return;
    }

    setIsLoadingSavedChats(true);

    try {
      const savedConversationList =
        await getSavedConversations(authToken);
      setSavedChats(savedConversationList.conversations);
      setSavedChatsLimit(savedConversationList.max_saved_chats);
    } catch {
      if (showError) {
        setError(
          "Saved chats could not be loaded. You can still continue this conversation.",
        );
      }
    } finally {
      setIsLoadingSavedChats(false);
    }
  }

  function startNewChat() {
    const nextSessionId = createId();
    saveSessionId(nextSessionId);
    setSessionId(nextSessionId);
    setMessages([]);
    setDraft("");
    setError(null);
    setIsSavedChatsOpen(false);
    inputRef.current?.focus();
  }

  function openSavedChat(sessionIdToOpen: string) {
    saveSessionId(sessionIdToOpen);
    setSessionId(sessionIdToOpen);
    setDraft("");
    setError(null);
    setIsSavedChatsOpen(false);
  }

  async function deleteSavedChat(sessionIdToDelete: string) {
    if (!authToken) {
      return;
    }

    try {
      await deleteSavedConversation(sessionIdToDelete, authToken);

      if (sessionIdToDelete === sessionId) {
        startNewChat();
      }

      await refreshSavedChats(false);
    } catch {
      setError("Saved chat could not be deleted.");
    }
  }

  async function submitMessage(
    rawMessage: string,
    options: {
      appendUser?: boolean;
      historyOverride?: ChatMessage[];
    } = {},
  ) {
    if (!authToken) {
      setError("Sign in to send and save chats.");
      return;
    }

    const message = rawMessage.trim();

    if (!message || isSending) {
      return;
    }

    const shouldAppendUser = options.appendUser !== false;
    const previousHistory = options.historyOverride ?? history;
    const userMessageId = createId();

    if (shouldAppendUser) {
      setMessages((current) => [
        ...current,
        {
          id: userMessageId,
          role: "user",
          content: message,
          createdAt: new Date().toISOString(),
        },
      ]);
    }
    setDraft("");
    setError(null);
    setIsSending(true);

    try {
      const response = await sendChatMessage(
        message,
        previousHistory,
        sessionId,
        authToken,
      );

      setMessages((current) => [
        ...current,
        {
          id: createId(),
          role: "assistant",
          content: response.reply,
          riskLevel: response.risk_level,
          createdAt: new Date().toISOString(),
        },
      ]);

      if (!response.saved) {
        setError(
          "Reply received, but this exchange could not be saved.",
        );
      } else {
        void refreshSavedChats(false);
      }
    } catch (caughtError) {
      const messageText =
        caughtError instanceof Error
          ? caughtError.message
          : "An unexpected error occurred.";

      setError(messageText);
      if (shouldAppendUser) {
        setMessages((current) =>
          current.map((message) =>
            message.id === userMessageId
              ? { ...message, status: "failed" }
              : message,
          ),
        );
      }
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  }

  async function retryMessage(message: DisplayMessage) {
    setMessages((current) =>
      current.filter((currentMessage) => currentMessage.id !== message.id),
    );
    await submitMessage(message.content);
  }

  async function regenerateLastReply() {
    if (isSending) {
      return;
    }

    const lastUserIndex = [...messages]
      .map((message, index) => ({ message, index }))
      .reverse()
      .find(({ message }) => message.role === "user")?.index;

    if (lastUserIndex === undefined) {
      return;
    }

    const lastUserMessage = messages[lastUserIndex];
    const historyBeforeUser = messages
      .slice(0, lastUserIndex)
      .map(({ role, content }) => ({ role, content }));

    setMessages(messages.slice(0, lastUserIndex + 1));
    await submitMessage(lastUserMessage.content, {
      appendUser: false,
      historyOverride: historyBeforeUser,
    });
  }

  async function copyMessage(content: string) {
    try {
      await navigator.clipboard.writeText(content);
    } catch {
      setError("Message could not be copied.");
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitMessage(draft);
  }

  function handleKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitMessage(draft);
    }
  }

  async function clearConversation() {
    setMessages([]);
    setError(null);
    setDraft("");
    inputRef.current?.focus();

    if (!authToken) {
      return;
    }

    try {
      await deleteSavedConversation(sessionId, authToken);
      await refreshSavedChats(false);
    } catch {
      setError(
        "The chat was cleared here, but the saved copy could not be deleted.",
      );
    }
  }

  async function exportSavedChats() {
    if (!authToken) {
      return;
    }

    try {
      const exportPayload = await exportAccountData(authToken);
      const blob = new Blob(
        [JSON.stringify(exportPayload, null, 2)],
        {
          type: "application/json",
        },
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `emotional-support-export-${new Date()
        .toISOString()
        .slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Saved chats could not be exported.");
    }
  }

  async function deleteAccount() {
    if (!authToken) {
      return;
    }

    const confirmed = window.confirm(
      "Delete this account and all saved chats? This cannot be undone.",
    );
    if (!confirmed) {
      return;
    }

    try {
      await deleteAccountData(authToken);
      signOut();
    } catch {
      setError("Account data could not be deleted.");
    }
  }

  function signOut() {
    clearAuth();
    setAuthToken(null);
    setCurrentUser(null);
    setMessages([]);
    setSavedChats([]);
    setDraft("");
    setError(null);
    setIsSettingsOpen(false);
    setIsSavedChatsOpen(false);
    startNewChat();
  }

  if (!authToken || !currentUser) {
    return (
      <AuthPanel
        mode={authMode}
        onModeChange={setAuthMode}
        onSubmit={handleAuthSubmit}
        onDevLogin={handleDevLogin}
        isSubmitting={isAuthenticating}
        error={authError}
      />
    );
  }

  return (
    <main className="app-shell">
      <div className="chat-layout">
        <aside className="saved-sidebar" aria-labelledby="sidebar-heading">
          <div className="saved-sidebar-header">
            <div>
              <h2 id="sidebar-heading">Saved chats</h2>
              <p>
                {savedChats.length}/{savedChatsLimit} saved
              </p>
            </div>

            <button
              className="primary-button compact-button"
              type="button"
              onClick={startNewChat}
              disabled={isSending}
            >
              New
            </button>
          </div>

          <label className="sidebar-search">
            Search chats
            <input
              value={savedChatSearch}
              onChange={(event) => setSavedChatSearch(event.target.value)}
              placeholder="Search saved chats"
            />
          </label>

          <div className="sidebar-list" aria-label="Saved chats">
            {isLoadingSavedChats ? (
              <div className="saved-chats-empty">Loading saved chats...</div>
            ) : filteredSavedChats.length === 0 ? (
              <div className="saved-chats-empty">
                {savedChatSearch
                  ? "No saved chats match your search."
                  : "Saved chats will appear here after a reply is stored."}
              </div>
            ) : (
              filteredSavedChats.map((chat) => (
                <article
                  key={chat.session_id}
                  className={
                    chat.session_id === sessionId
                      ? "sidebar-chat active"
                      : "sidebar-chat"
                  }
                >
                  <button
                    type="button"
                    className="sidebar-chat-open"
                    onClick={() => openSavedChat(chat.session_id)}
                  >
                    <span className="saved-chat-title">{chat.title}</span>
                    <span className="saved-chat-preview">
                      {chat.last_message_preview}
                    </span>
                    <span className="saved-chat-meta">
                      {chat.message_count} messages ·{" "}
                      {formatSavedDate(chat.updated_at)}
                    </span>
                  </button>

                  <button
                    type="button"
                    className="saved-chat-delete icon-delete"
                    onClick={() => void deleteSavedChat(chat.session_id)}
                    aria-label={`Delete saved chat: ${chat.title}`}
                  >
                    Delete
                  </button>
                </article>
              ))
            )}
          </div>
        </aside>

        <section className="chat-card">
        <header className="app-header">
          <div>
            <p className="eyebrow">Safety-aware AI demo</p>
            <h1>Emotional Support Guide</h1>
            <p className="subtitle">
              Signed in as {currentUser.display_name}.
            </p>
          </div>

          <div className="header-actions">
            <button
              className="secondary-button mobile-saved-toggle"
              type="button"
              onClick={() =>
                setIsSavedChatsOpen((current) => !current)
              }
              aria-expanded={isSavedChatsOpen}
              aria-controls="saved-chats-panel"
            >
              Saved chats
            </button>

            <button
              className="secondary-button"
              type="button"
              onClick={startNewChat}
              disabled={isSending}
            >
              New chat
            </button>

            <button
              className="secondary-button"
              type="button"
              onClick={() =>
                setIsSettingsOpen((current) => !current)
              }
              aria-expanded={isSettingsOpen}
              aria-controls="settings-panel"
            >
              Settings
            </button>

            <button
              className="secondary-button"
              type="button"
              onClick={() => void clearConversation()}
              disabled={messages.length === 0 || isSending}
            >
              Clear chat
            </button>
          </div>
        </header>

        {isSavedChatsOpen && (
          <section
            id="saved-chats-panel"
            className="saved-chats-panel"
            aria-labelledby="saved-chats-heading"
          >
            <div className="saved-chats-header">
              <div>
                <h2 id="saved-chats-heading">Saved chats</h2>
                <p>
                  {savedChats.length}/{savedChatsLimit} saved
                </p>
              </div>

              <div className="saved-chats-actions">
                <button
                  className="secondary-button compact-button"
                  type="button"
                  onClick={startNewChat}
                  disabled={isSending}
                >
                  New chat
                </button>

                <button
                  className="secondary-button compact-button"
                  type="button"
                  onClick={() => setIsSavedChatsOpen(false)}
                >
                  Close
                </button>
              </div>
            </div>

            <label className="sidebar-search panel-search">
              Search chats
              <input
                value={savedChatSearch}
                onChange={(event) =>
                  setSavedChatSearch(event.target.value)
                }
                placeholder="Search saved chats"
              />
            </label>

            {isLoadingSavedChats ? (
              <div className="saved-chats-empty">
                Loading saved chats...
              </div>
            ) : filteredSavedChats.length === 0 ? (
              <div className="saved-chats-empty">
                {savedChatSearch
                  ? "No saved chats match your search."
                  : "Saved chats will appear here after a reply is stored."}
              </div>
            ) : (
              <div
                className="saved-chat-list"
                aria-label="Saved chats"
              >
                {filteredSavedChats.map((chat) => (
                  <article
                    key={chat.session_id}
                    className={
                      chat.session_id === sessionId
                        ? "saved-chat-item active"
                        : "saved-chat-item"
                    }
                  >
                    <button
                      type="button"
                      className="saved-chat-open"
                      onClick={() =>
                        openSavedChat(chat.session_id)
                      }
                    >
                      <span className="saved-chat-title">
                        {chat.title}
                      </span>
                      <span className="saved-chat-preview">
                        {chat.last_message_preview}
                      </span>
                      <span className="saved-chat-meta">
                        {chat.message_count} messages · Updated{" "}
                        {formatSavedDate(chat.updated_at)} · Expires{" "}
                        {formatSavedDate(chat.expires_at)}
                      </span>
                    </button>

                    <button
                      type="button"
                      className="saved-chat-delete"
                      onClick={() =>
                        void deleteSavedChat(chat.session_id)
                      }
                      aria-label={`Delete saved chat: ${chat.title}`}
                    >
                      Delete
                    </button>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {isSettingsOpen && (
          <section
            id="settings-panel"
            className="settings-panel"
            aria-labelledby="settings-heading"
          >
            <div className="settings-header">
              <div>
                <h2 id="settings-heading">Settings</h2>
                <p>{settingsTab[0].toUpperCase() + settingsTab.slice(1)}</p>
              </div>

              <button
                className="secondary-button compact-button"
                type="button"
                onClick={() => setIsSettingsOpen(false)}
              >
                Close
              </button>
            </div>

            <div className="settings-tabs" role="tablist">
              {(["general", "account", "privacy", "safety"] as SettingsTab[]).map(
                (tabName) => (
                  <button
                    key={tabName}
                    type="button"
                    role="tab"
                    aria-selected={settingsTab === tabName}
                    className={settingsTab === tabName ? "active" : undefined}
                    onClick={() => setSettingsTab(tabName)}
                  >
                    {tabName[0].toUpperCase() + tabName.slice(1)}
                  </button>
                ),
              )}
            </div>

            {settingsTab === "general" && (
              <div className="setting-row">
                <div>
                  <h3>Display mode</h3>
                  <p>Choose how the app appears on this device.</p>
                </div>

                <div
                  className="segmented-control"
                  role="group"
                  aria-label="Display mode"
                >
                  <button
                    type="button"
                    className={
                      displayMode === "light" ? "active" : undefined
                    }
                    aria-pressed={displayMode === "light"}
                    onClick={() => setDisplayMode("light")}
                  >
                    Light
                  </button>

                  <button
                    type="button"
                    className={
                      displayMode === "dark" ? "active" : undefined
                    }
                    aria-pressed={displayMode === "dark"}
                    onClick={() => setDisplayMode("dark")}
                  >
                    Dark
                  </button>
                </div>
              </div>
            )}

            {settingsTab === "account" && (
              <div className="setting-row">
                <div>
                  <h3>Account</h3>
                  <p>{currentUser.email}</p>
                </div>

                <button
                  className="secondary-button"
                  type="button"
                  onClick={signOut}
                >
                  Log out
                </button>
              </div>
            )}

            {settingsTab === "privacy" && (
              <div className="setting-row">
                <div>
                  <h3>Privacy</h3>
                  <p>Export saved chats or delete your account data.</p>
                </div>

                <div className="privacy-actions">
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => void exportSavedChats()}
                  >
                    Export chats
                  </button>

                  <button
                    className="danger-button"
                    type="button"
                    onClick={() => void deleteAccount()}
                  >
                    Delete account
                  </button>
                </div>
              </div>
            )}

            {settingsTab === "safety" && (
              <div className="setting-row safety-setting">
                <div>
                  <h3>Safety resources</h3>
                  <p>
                    If there is immediate danger, contact emergency services.
                    In the U.S., 988 offers free crisis support.
                  </p>
                </div>

                <div className="crisis-actions">
                  <a className="crisis-action" href="tel:988">
                    Call 988
                  </a>
                  <a className="crisis-action" href="sms:988">
                    Text 988
                  </a>
                  <a
                    className="crisis-action"
                    href="https://chat.988lifeline.org/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open 988 chat
                  </a>
                </div>
              </div>
            )}
          </section>
        )}

        {hasCrisisRisk && (
          <section className="crisis-panel" role="alert">
            <div>
              <strong>Immediate support is available.</strong>
              <p>
                If you might hurt yourself or someone else, call emergency
                services now. In the U.S., the 988 Lifeline can be reached
                by call, text, or chat.
              </p>
            </div>

            <div className="crisis-actions">
              <a className="crisis-action" href="tel:988">
                Call 988
              </a>
              <a className="crisis-action" href="sms:988">
                Text 988
              </a>
              <a
                className="crisis-action"
                href="https://chat.988lifeline.org/"
                target="_blank"
                rel="noreferrer"
              >
                Open 988 chat
              </a>
            </div>
          </section>
        )}

        <div className="notice" role="note">
          This assistant is not a therapist, diagnostic tool, or
          emergency service. Do not share identifying or highly
          sensitive information in this development demo. Chats are
          saved to your account for up to 10 days.
        </div>

        <div
          className="messages"
          aria-live="polite"
          aria-label="Conversation"
        >
          {messages.length === 0 ? (
            <div className="empty-state">
              <h2>What would help right now?</h2>
              <p>
                Choose a prompt or write your own message below.
              </p>

              <div className="prompt-grid">
                {starterPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    className="prompt-button"
                    onClick={() => void submitMessage(prompt)}
                    disabled={isSending}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message, index) => {
              const isLastAssistant =
                message.role === "assistant" &&
                index === messages.length - 1;

              return (
                <article
                  key={message.id}
                  className={`message ${message.role} ${
                    message.status === "failed" ? "failed" : ""
                  }`}
                >
                  <div className="message-heading">
                    <div className="message-heading-main">
                      <strong>
                        {message.role === "user" ? "You" : "Guide"}
                      </strong>
                      <span>{formatMessageTime(message.createdAt)}</span>

                      {message.role === "assistant" &&
                        message.riskLevel &&
                        message.riskLevel !== "standard" && (
                          <span
                            className={`risk-badge ${message.riskLevel}`}
                          >
                            {message.riskLevel}
                          </span>
                        )}
                    </div>

                    <div className="message-actions">
                      <button
                        type="button"
                        onClick={() => void copyMessage(message.content)}
                      >
                        Copy
                      </button>
                      {message.status === "failed" && (
                        <button
                          type="button"
                          onClick={() => void retryMessage(message)}
                        >
                          Retry
                        </button>
                      )}
                      {isLastAssistant && (
                        <button
                          type="button"
                          onClick={() => void regenerateLastReply()}
                          disabled={isSending}
                        >
                          Regenerate
                        </button>
                      )}
                    </div>
                  </div>

                  <MessageContent
                    content={message.content}
                    role={message.role}
                  />

                  {message.status === "failed" && (
                    <p className="message-status">
                      This message did not send.
                    </p>
                  )}
                </article>
              );
            })
          )}

          {isSending && (
            <article className="message assistant loading-message">
              <strong>Guide</strong>
              <p>Thinking carefully...</p>
            </article>
          )}
        </div>

        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}

        <form className="composer" onSubmit={handleSubmit}>
          <label htmlFor="message">Your message</label>

          <textarea
            ref={inputRef}
            id="message"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Write what is happening or ask for a coping strategy..."
            maxLength={4000}
            rows={4}
            disabled={isSending}
          />

          <div className="composer-footer">
            <span>{draft.length}/4000</span>
            <button
              className="primary-button"
              type="submit"
              disabled={!draft.trim() || isSending}
            >
              {isSending ? "Sending..." : "Send"}
            </button>
          </div>
        </form>
        </section>
      </div>
    </main>
  );
}
