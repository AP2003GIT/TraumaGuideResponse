import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  confirmPasswordReset,
  deleteAccountData,
  deleteSavedConversation,
  exportAccountData,
  getAdminDashboard,
  getCurrentUser,
  getSavedConversation,
  getSavedConversations,
  continueAsDeveloper,
  loginAccount,
  registerAccount,
  requestPasswordReset,
  sendChatMessage,
  updateAccountProfile,
} from "./api";
import type {
  AdminDashboard,
  AuthenticatedUser,
  ChatMessage,
  SavedConversationSummary,
} from "./types";
import {
  clearAuth,
  getSavedAuth,
  getSavedDisplayMode,
  isAuthRemembered,
  saveAuth,
  saveDisplayMode,
  type DisplayMode,
} from "./authStorage";
import {
  createId,
  formatMessageTime,
  getSavedSessionId,
  saveSessionId,
  toDisplayMessage,
  type DisplayMessage,
} from "./chatHelpers";
import { AuthPanel, type AuthMode } from "./components/AuthPanel";
import { MessageContent } from "./components/MessageContent";
import {
  SavedChatsPanel,
  SavedChatsSidebar,
} from "./components/SavedChats";
import {
  SettingsPanel,
  type ExportScope,
  type SettingsTab,
} from "./components/SettingsPanel";

const starterPrompts = [
  "I feel overwhelmed and need a grounding exercise.",
  "Help me understand why stress affects my sleep.",
  "How can I communicate a boundary calmly?",
];

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
  const [profileName, setProfileName] = useState(
    savedAuth.user?.display_name ?? "",
  );
  const [profileEmail, setProfileEmail] = useState(
    savedAuth.user?.email ?? "",
  );
  const [profileCurrentPassword, setProfileCurrentPassword] = useState("");
  const [profileNewPassword, setProfileNewPassword] = useState("");
  const [profileStatus, setProfileStatus] = useState<string | null>(null);
  const [exportScope, setExportScope] = useState<ExportScope>("all");
  const [exportFromDate, setExportFromDate] = useState("");
  const [exportToDate, setExportToDate] = useState("");
  const [adminDashboard, setAdminDashboard] =
    useState<AdminDashboard | null>(null);
  const [isLoadingAdminDashboard, setIsLoadingAdminDashboard] =
    useState(false);
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
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
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
  const settingsTabs = useMemo<SettingsTab[]>(
    () =>
      currentUser?.role === "admin"
        ? ["general", "account", "privacy", "safety", "admin"]
        : ["general", "account", "privacy", "safety"],
    [currentUser?.role],
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
    saveDisplayMode(displayMode);
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

    async function refreshCurrentUser() {
      try {
        const user = await getCurrentUser(token);
        if (isCancelled) {
          return;
        }

        setCurrentUser(user);
        saveAuth(token, user, isAuthRemembered());
      } catch {
        if (!isCancelled) {
          clearAuth();
          setAuthToken(null);
          setCurrentUser(null);
        }
      }
    }

    void refreshCurrentUser();

    return () => {
      isCancelled = true;
    };
  }, [authToken]);

  useEffect(() => {
    if (currentUser) {
      setProfileName(currentUser.display_name);
      setProfileEmail(currentUser.email);
    }
  }, [currentUser]);

  useEffect(() => {
    if (settingsTab === "admin" && authToken) {
      void refreshAdminDashboard();
    }
  }, [settingsTab, authToken]);

  useEffect(() => {
    if (settingsTab === "admin" && currentUser?.role !== "admin") {
      setSettingsTab("general");
    }
  }, [currentUser?.role, settingsTab]);

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

  async function handlePasswordResetRequest(
    email: string,
  ): Promise<string | null> {
    setIsAuthenticating(true);
    setAuthError(null);

    try {
      const response = await requestPasswordReset(email);
      return response.dev_reset_token;
    } catch (caughtError) {
      setAuthError(
        caughtError instanceof Error
          ? caughtError.message
          : "Password reset could not be started.",
      );
      return null;
    } finally {
      setIsAuthenticating(false);
    }
  }

  async function handlePasswordResetConfirm(
    resetToken: string,
    newPassword: string,
    rememberMe: boolean,
  ) {
    setIsAuthenticating(true);
    setAuthError(null);

    try {
      const response = await confirmPasswordReset(
        resetToken,
        newPassword,
      );

      saveAuth(response.access_token, response.user, rememberMe);
      setAuthToken(response.access_token);
      setCurrentUser(response.user);
      setMessages([]);
      setError(null);
    } catch (caughtError) {
      setAuthError(
        caughtError instanceof Error
          ? caughtError.message
          : "Password reset failed.",
      );
    } finally {
      setIsAuthenticating(false);
    }
  }

  async function saveProfile() {
    if (!authToken) {
      return;
    }

    setProfileStatus(null);
    setError(null);

    try {
      const response = await updateAccountProfile(
        authToken,
        profileName,
        profileEmail,
        profileCurrentPassword,
        profileNewPassword,
      );

      saveAuth(response.access_token, response.user, isAuthRemembered());
      setAuthToken(response.access_token);
      setCurrentUser(response.user);
      setProfileCurrentPassword("");
      setProfileNewPassword("");
      setProfileStatus("Profile updated.");
    } catch (caughtError) {
      setProfileStatus(
        caughtError instanceof Error
          ? caughtError.message
          : "Profile could not be updated.",
      );
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

  async function refreshAdminDashboard() {
    if (!authToken) {
      return;
    }

    setIsLoadingAdminDashboard(true);

    try {
      setAdminDashboard(await getAdminDashboard(authToken));
    } catch {
      setError("Admin dashboard could not be loaded.");
    } finally {
      setIsLoadingAdminDashboard(false);
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
      setStatusMessage("Message copied.");
      window.setTimeout(() => setStatusMessage(null), 1800);
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
      const from = exportFromDate
        ? new Date(`${exportFromDate}T00:00:00`)
        : null;
      const to = exportToDate
        ? new Date(`${exportToDate}T23:59:59`)
        : null;
      const filteredConversations = exportPayload.conversations.filter(
        (conversation) => {
          if (
            exportScope === "current" &&
            conversation.session_id !== sessionId
          ) {
            return false;
          }

          const updatedAt = new Date(conversation.updated_at);
          if (from && updatedAt < from) {
            return false;
          }

          if (to && updatedAt > to) {
            return false;
          }

          return true;
        },
      );
      const filteredExport = {
        ...exportPayload,
        conversations: filteredConversations,
      };
      const blob = new Blob(
        [JSON.stringify(filteredExport, null, 2)],
        {
          type: "application/json",
        },
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `emotional-support-${exportScope}-export-${new Date()
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
        onRequestReset={handlePasswordResetRequest}
        onConfirmReset={handlePasswordResetConfirm}
        isSubmitting={isAuthenticating}
        error={authError}
      />
    );
  }

  return (
    <main className="app-shell">
      <div className="chat-layout">
        <SavedChatsSidebar
          chats={filteredSavedChats}
          activeSessionId={sessionId}
          savedChatsCount={savedChats.length}
          savedChatsLimit={savedChatsLimit}
          search={savedChatSearch}
          onSearchChange={setSavedChatSearch}
          onOpenChat={openSavedChat}
          onDeleteChat={(sessionIdToDelete) =>
            void deleteSavedChat(sessionIdToDelete)
          }
          onStartNewChat={startNewChat}
          isLoading={isLoadingSavedChats}
          isSending={isSending}
        />

        <section className="chat-card">
        <header className="app-header">
          <div>
            <p className="eyebrow">Safety-aware AI demo</p>
            <h1>Emotional Support Guide</h1>
            <p className="subtitle">
              Signed in as {currentUser.display_name}.{" "}
              {currentUser.role === "admin" && (
                <span className="role-chip">Admin</span>
              )}
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
          <SavedChatsPanel
            chats={filteredSavedChats}
            activeSessionId={sessionId}
            savedChatsCount={savedChats.length}
            savedChatsLimit={savedChatsLimit}
            search={savedChatSearch}
            onSearchChange={setSavedChatSearch}
            onOpenChat={openSavedChat}
            onDeleteChat={(sessionIdToDelete) =>
              void deleteSavedChat(sessionIdToDelete)
            }
            onStartNewChat={startNewChat}
            onClose={() => setIsSavedChatsOpen(false)}
            isLoading={isLoadingSavedChats}
            isSending={isSending}
          />
        )}

        {isSettingsOpen && (
          <SettingsPanel
            activeTab={settingsTab}
            tabs={settingsTabs}
            displayMode={displayMode}
            profileName={profileName}
            profileEmail={profileEmail}
            profileCurrentPassword={profileCurrentPassword}
            profileNewPassword={profileNewPassword}
            profileStatus={profileStatus}
            exportScope={exportScope}
            exportFromDate={exportFromDate}
            exportToDate={exportToDate}
            adminDashboard={adminDashboard}
            isLoadingAdminDashboard={isLoadingAdminDashboard}
            onClose={() => setIsSettingsOpen(false)}
            onTabChange={setSettingsTab}
            onDisplayModeChange={setDisplayMode}
            onProfileNameChange={setProfileName}
            onProfileEmailChange={setProfileEmail}
            onProfileCurrentPasswordChange={setProfileCurrentPassword}
            onProfileNewPasswordChange={setProfileNewPassword}
            onExportScopeChange={setExportScope}
            onExportFromDateChange={setExportFromDate}
            onExportToDateChange={setExportToDate}
            onSaveProfile={() => void saveProfile()}
            onSignOut={signOut}
            onExportSavedChats={() => void exportSavedChats()}
            onDeleteAccount={() => void deleteAccount()}
            onRefreshAdminDashboard={() => void refreshAdminDashboard()}
          />
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

        {statusMessage && (
          <div className="status-toast" role="status">
            {statusMessage}
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
