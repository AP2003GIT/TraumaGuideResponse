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
  getDependencyStatus,
  getSavedConversation,
  getSavedConversations,
  continueAsDeveloper,
  loginAccount,
  registerAccount,
  requestPasswordReset,
  sendChatMessage,
  updateAccountProfile,
  updateSavedConversationMetadata,
} from "./api";
import type {
  AdminDashboard,
  AuthenticatedUser,
  ChatMessage,
  DependencyStatus,
  SavedConversationSummary,
  ServiceMode,
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

// Prompt groups shown in the empty chat state. Clicking one fills the draft
// instead of sending immediately so the user can personalize it first.
const starterPrompts = [
  {
    category: "Grounding",
    prompts: [
      "I feel overwhelmed and need a grounding exercise.",
      "Walk me through a quick body scan.",
      "Help me calm down before I reply to someone.",
    ],
  },
  {
    category: "Reflection",
    prompts: [
      "Help me name what I am feeling right now.",
      "Help me understand why stress affects my sleep.",
      "What questions can I ask myself when I feel stuck?",
    ],
  },
  {
    category: "Communication",
    prompts: [
      "How can I communicate a boundary calmly?",
      "Help me write a short message asking for space.",
      "Help me prepare for a difficult conversation.",
    ],
  },
];

const PINNED_CHAT_IDS_KEY = "trauma-guide-pinned-chat-ids";
const CHAT_DRAFTS_KEY = "trauma-guide-chat-drafts";

type SavedChatFilter = "all" | "pinned" | "expiring";

// Saved-chat pins are mirrored in local storage so the sidebar feels stable
// immediately, then refreshed from the backend when saved chats reload.
function getPinnedSavedChatIds(): string[] {
  try {
    const rawValue = window.localStorage.getItem(PINNED_CHAT_IDS_KEY);
    const parsedValue = rawValue ? JSON.parse(rawValue) : [];
    return Array.isArray(parsedValue)
      ? parsedValue.filter((value) => typeof value === "string")
      : [];
  } catch {
    return [];
  }
}

function savePinnedSavedChatIds(sessionIds: string[]) {
  window.localStorage.setItem(
    PINNED_CHAT_IDS_KEY,
    JSON.stringify(sessionIds),
  );
}

// Drafts are stored by session id, which lets the user switch chats without
// losing unsent text in the composer.
function getSavedDrafts(): Record<string, string> {
  try {
    const rawValue = window.localStorage.getItem(CHAT_DRAFTS_KEY);
    const parsedValue = rawValue ? JSON.parse(rawValue) : {};

    if (!parsedValue || typeof parsedValue !== "object") {
      return {};
    }

    return Object.entries(parsedValue).reduce<Record<string, string>>(
      (drafts, [sessionId, value]) => {
        if (typeof value === "string") {
          drafts[sessionId] = value;
        }

        return drafts;
      },
      {},
    );
  } catch {
    return {};
  }
}

function saveDrafts(drafts: Record<string, string>) {
  window.localStorage.setItem(CHAT_DRAFTS_KEY, JSON.stringify(drafts));
}

function getDaysUntilExpiration(chat: SavedConversationSummary): number {
  const expiresAt = new Date(chat.expires_at).getTime();
  return Math.ceil((expiresAt - Date.now()) / 86400000);
}

function getServiceMode(
  dependencies: DependencyStatus | null,
): ServiceMode {
  if (!dependencies) {
    return "checking";
  }

  if (dependencies.mode) {
    return dependencies.mode;
  }

  if (dependencies.gateway !== "healthy") {
    return "offline";
  }

  const downstreamStatuses = [
    dependencies.safety_service,
    dependencies.chat_service,
    dependencies.save_service,
  ];

  return downstreamStatuses.every((service) => service === "healthy")
    ? "live"
    : "fallback";
}

// These small helpers keep service health wording consistent between the
// header chip and the admin diagnostics panel.
function getServiceModeLabel(mode: ServiceMode): string {
  switch (mode) {
    case "live":
      return "Live services";
    case "fallback":
      return "Fallback mode";
    case "offline":
      return "Offline";
    default:
      return "Checking services";
  }
}

function getServiceModeDetail(mode: ServiceMode): string {
  switch (mode) {
    case "live":
      return "Safety, chat, and saving services are healthy.";
    case "fallback":
      return "A dependency is unavailable, so the demo fallback is active.";
    case "offline":
      return "The gateway health check is not reachable.";
    default:
      return "Checking gateway and dependency health.";
  }
}

export default function App() {
  const savedAuth = getSavedAuth();

  // Core session and authentication state. Remembered auth is restored from
  // browser storage before the first render.
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

  // UI state for panels, saved-chat filters, and account settings forms.
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("general");
  const [savedChatSearch, setSavedChatSearch] = useState("");
  const [savedChatFilter, setSavedChatFilter] =
    useState<SavedChatFilter>("all");
  const [activePromptCategory, setActivePromptCategory] =
    useState(starterPrompts[0].category);
  const [pinnedSavedChatIds, setPinnedSavedChatIds] = useState(
    getPinnedSavedChatIds,
  );
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

  // Conversation state. The message list is the visible chat transcript;
  // saved chat summaries power the sidebar and mobile saved-chat panel.
  const [savedChats, setSavedChats] = useState<
    SavedConversationSummary[]
  >([]);
  const [savedChatsLimit, setSavedChatsLimit] = useState(10);
  const [isLoadingSavedChats, setIsLoadingSavedChats] =
    useState(false);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [draftsBySession, setDraftsBySession] = useState(getSavedDrafts);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [dependencyStatus, setDependencyStatus] =
    useState<DependencyStatus | null>(null);
  const [serviceMode, setServiceMode] =
    useState<ServiceMode>("checking");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // The backend wants compact role/content history, not the extra display
  // fields we keep for timestamps, status labels, and risk badges.
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
  const pinnedSavedChatIdSet = useMemo(
    () => new Set(pinnedSavedChatIds),
    [pinnedSavedChatIds],
  );
  const draft = draftsBySession[sessionId] ?? "";
  const activePromptGroup =
    starterPrompts.find(
      (promptGroup) => promptGroup.category === activePromptCategory,
    ) ?? starterPrompts[0];
  const activeSavedChat = savedChats.find(
    (chat) => chat.session_id === sessionId,
  );
  const userMessageCount = messages.filter(
    (message) => message.role === "user",
  ).length;
  const assistantMessageCount = messages.filter(
    (message) => message.role === "assistant",
  ).length;

  // Saved chats are filtered client-side so search/filter clicks do not need
  // a network round trip.
  const filteredSavedChats = useMemo(
    () => {
      const filteredChats = savedChats.filter((chat) => {
        const query = savedChatSearch.trim().toLowerCase();
        const isPinned = pinnedSavedChatIdSet.has(chat.session_id);
        const isExpiringSoon = getDaysUntilExpiration(chat) <= 3;

        if (savedChatFilter === "pinned" && !isPinned) {
          return false;
        }

        if (savedChatFilter === "expiring" && !isExpiringSoon) {
          return false;
        }

        if (query) {
          return (
            chat.title.toLowerCase().includes(query) ||
            chat.last_message_preview.toLowerCase().includes(query)
          );
        }

        return true;
      });

      return filteredChats.sort((left, right) => {
        const leftPinned = pinnedSavedChatIdSet.has(left.session_id);
        const rightPinned = pinnedSavedChatIdSet.has(right.session_id);

        if (leftPinned !== rightPinned) {
          return leftPinned ? -1 : 1;
        }

        return (
          new Date(right.updated_at).getTime() -
          new Date(left.updated_at).getTime()
        );
      });
    },
    [
      pinnedSavedChatIdSet,
      savedChatFilter,
      savedChatSearch,
      savedChats,
    ],
  );

  useEffect(() => {
    let isCancelled = false;

    async function refreshServiceStatus() {
      try {
        const dependencies = await getDependencyStatus();
        if (!isCancelled) {
          setDependencyStatus(dependencies);
          setServiceMode(getServiceMode(dependencies));
        }
      } catch {
        if (!isCancelled) {
          setDependencyStatus(null);
          setServiceMode("offline");
        }
      }
    }

    void refreshServiceStatus();
    const intervalId = window.setInterval(refreshServiceStatus, 30000);

    return () => {
      isCancelled = true;
      window.clearInterval(intervalId);
    };
  }, []);

  // Apply the selected theme at the document level so every component can use
  // the same CSS variables.
  useEffect(() => {
    document.documentElement.dataset.theme = displayMode;
    document.documentElement.style.colorScheme = displayMode;
    saveDisplayMode(displayMode);
  }, [displayMode]);

  // Saved chats load on sign-in and when the saved-chat panel opens.
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

  // Validate remembered tokens against the backend. If the token is stale,
  // clear it and send the user back to the auth screen.
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

  // Admin data is loaded lazily because normal users never need this request.
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

  // When the active session changes, hydrate the transcript from saved chat
  // storage if the backend still has it.
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

  // Authentication handlers centralize login/register/dev-login flows and set
  // the same app state no matter which auth path succeeds.
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

  // Saved-chat summary data drives the sidebar, stats strip, and pin state.
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
      const pinnedIds = savedConversationList.conversations
        .filter((conversation) => conversation.pinned)
        .map((conversation) => conversation.session_id);
      setPinnedSavedChatIds(pinnedIds);
      savePinnedSavedChatIds(pinnedIds);
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

  // Draft helpers keep the composer synced with local storage per session.
  function updateDraft(nextDraft: string) {
    setDraftsBySession((currentDrafts) => {
      const nextDrafts = { ...currentDrafts };

      if (nextDraft) {
        nextDrafts[sessionId] = nextDraft;
      } else {
        delete nextDrafts[sessionId];
      }

      saveDrafts(nextDrafts);
      return nextDrafts;
    });
  }

  function usePrompt(prompt: string) {
    updateDraft(prompt);
    inputRef.current?.focus();
  }

  // Chat navigation changes the session id and lets the saved-conversation
  // effect decide whether there is a transcript to load.
  function startNewChat() {
    const nextSessionId = createId();
    saveSessionId(nextSessionId);
    setSessionId(nextSessionId);
    setMessages([]);
    updateDraft("");
    setError(null);
    setIsSavedChatsOpen(false);
    inputRef.current?.focus();
  }

  function openSavedChat(sessionIdToOpen: string) {
    saveSessionId(sessionIdToOpen);
    setSessionId(sessionIdToOpen);
    setError(null);
    setIsSavedChatsOpen(false);
  }

  async function togglePinnedSavedChat(sessionIdToToggle: string) {
    if (!authToken) {
      return;
    }

    const shouldPin = !pinnedSavedChatIdSet.has(sessionIdToToggle);

    setPinnedSavedChatIds((current) => {
      const next = current.includes(sessionIdToToggle)
        ? current.filter((sessionId) => sessionId !== sessionIdToToggle)
        : [sessionIdToToggle, ...current];

      savePinnedSavedChatIds(next);
      return next;
    });
    setSavedChats((current) =>
      current.map((chat) =>
        chat.session_id === sessionIdToToggle
          ? { ...chat, pinned: shouldPin }
          : chat,
      ),
    );

    try {
      await updateSavedConversationMetadata(
        sessionIdToToggle,
        authToken,
        { pinned: shouldPin },
      );
      await refreshSavedChats(false);
    } catch (caughtError) {
      setPinnedSavedChatIds((current) => {
        const reverted = shouldPin
          ? current.filter((sessionId) => sessionId !== sessionIdToToggle)
          : [sessionIdToToggle, ...current];
        savePinnedSavedChatIds(reverted);
        return reverted;
      });
      setSavedChats((current) =>
        current.map((chat) =>
          chat.session_id === sessionIdToToggle
            ? { ...chat, pinned: !shouldPin }
            : chat,
        ),
      );
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Saved chat could not be updated.",
      );
    }
  }

  // Metadata edits are optimistic for quick UI feedback, then refreshed from
  // the backend/fallback store so server truth wins.
  async function renameSavedChat(
    sessionIdToRename: string,
    nextTitle: string,
  ) {
    if (!authToken) {
      return;
    }

    const cleanedTitle = nextTitle.trim();
    if (!cleanedTitle) {
      return;
    }

    setSavedChats((current) =>
      current.map((chat) =>
        chat.session_id === sessionIdToRename
          ? { ...chat, title: cleanedTitle }
          : chat,
      ),
    );

    try {
      await updateSavedConversationMetadata(
        sessionIdToRename,
        authToken,
        { title: cleanedTitle },
      );
      await refreshSavedChats(false);
      setStatusMessage("Saved chat renamed.");
      window.setTimeout(() => setStatusMessage(null), 1800);
    } catch (caughtError) {
      await refreshSavedChats(false);
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Saved chat could not be renamed.",
      );
    }
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

  // Main chat submit pipeline: optimistic user message, backend safety/chat
  // call, assistant message append, then saved-chat sidebar refresh.
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
    updateDraft("");
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
    updateDraft("");
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

  // Account privacy actions live here because they need the current filters,
  // current session id, and authenticated token.
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
    updateDraft("");
    setError(null);
    setIsSettingsOpen(false);
    setIsSavedChatsOpen(false);
    startNewChat();
  }

  // Unauthenticated users see only the auth panel. All app features below this
  // point assume there is a current user and bearer token.
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
        {/* Desktop saved-chat navigation. Mobile uses the collapsible panel. */}
        <SavedChatsSidebar
          chats={filteredSavedChats}
          activeSessionId={sessionId}
          savedChatsCount={savedChats.length}
          savedChatsLimit={savedChatsLimit}
          search={savedChatSearch}
          onSearchChange={setSavedChatSearch}
          filter={savedChatFilter}
          onFilterChange={setSavedChatFilter}
          pinnedChatIds={pinnedSavedChatIds}
          onTogglePinnedChat={(sessionIdToToggle) =>
            void togglePinnedSavedChat(sessionIdToToggle)
          }
          onRenameChat={(sessionIdToRename, nextTitle) =>
            void renameSavedChat(sessionIdToRename, nextTitle)
          }
          onOpenChat={openSavedChat}
          onDeleteChat={(sessionIdToDelete) =>
            void deleteSavedChat(sessionIdToDelete)
          }
          onStartNewChat={startNewChat}
          isLoading={isLoadingSavedChats}
          isSending={isSending}
        />

        <section className="chat-card">
        {/* Top-level app controls and service health chip. */}
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
            <div
              className={`service-mode service-mode-${serviceMode}`}
              title={getServiceModeDetail(serviceMode)}
            >
              <span aria-hidden="true" />
              <strong>{getServiceModeLabel(serviceMode)}</strong>
              {dependencyStatus && (
                <small>
                  Safety {dependencyStatus.safety_service} / Chat{" "}
                  {dependencyStatus.chat_service} / Save{" "}
                  {dependencyStatus.save_service}
                </small>
              )}
            </div>
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

        {/* Mobile saved-chat drawer, rendered only when toggled open. */}
        {isSavedChatsOpen && (
          <SavedChatsPanel
            chats={filteredSavedChats}
            activeSessionId={sessionId}
            savedChatsCount={savedChats.length}
            savedChatsLimit={savedChatsLimit}
            search={savedChatSearch}
            onSearchChange={setSavedChatSearch}
            filter={savedChatFilter}
            onFilterChange={setSavedChatFilter}
            pinnedChatIds={pinnedSavedChatIds}
            onTogglePinnedChat={(sessionIdToToggle) =>
              void togglePinnedSavedChat(sessionIdToToggle)
            }
            onRenameChat={(sessionIdToRename, nextTitle) =>
              void renameSavedChat(sessionIdToRename, nextTitle)
            }
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

        {/* Settings is kept in the page flow so it works on desktop and mobile. */}
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

        {/* High-risk assistant replies surface crisis resources above the chat. */}
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

        {/* Quick readout for the current conversation and saved-chat capacity. */}
        <section className="conversation-strip" aria-label="Conversation summary">
          <div>
            <span>Messages</span>
            <strong>{messages.length}</strong>
            <small>
              {userMessageCount} you / {assistantMessageCount} guide
            </small>
          </div>
          <div>
            <span>Saved chats</span>
            <strong>
              {savedChats.length}/{savedChatsLimit}
            </strong>
            <small>{savedChatsLimit - savedChats.length} slots open</small>
          </div>
          <div>
            <span>Retention</span>
            <strong>
              {activeSavedChat
                ? `${Math.max(getDaysUntilExpiration(activeSavedChat), 0)}d`
                : "10d"}
            </strong>
            <small>
              {activeSavedChat ? "until this chat expires" : "after saving"}
            </small>
          </div>
          <div>
            <span>Draft</span>
            <strong>{draft ? "Saved" : "Empty"}</strong>
            <small>{draft.length}/4000 characters</small>
          </div>
        </section>

        {/* Fast drafting buttons for common support workflows. */}
        <section className="support-tools" aria-label="Quick support tools">
          <button
            type="button"
            onClick={() =>
              usePrompt(
                "Guide me through a 60-second grounding exercise I can do right now.",
              )
            }
            disabled={isSending}
          >
            60-second grounding
          </button>
          <button
            type="button"
            onClick={() =>
              usePrompt(
                "Help me make a tiny next-step plan for the next ten minutes.",
              )
            }
            disabled={isSending}
          >
            Next-step plan
          </button>
          <button
            type="button"
            onClick={() =>
              usePrompt(
                "Help me rewrite this in a calmer and clearer way: ",
              )
            }
            disabled={isSending}
          >
            Calm rewrite
          </button>
        </section>

        {/* Transcript area. Empty chats show categorized starter prompts. */}
        <div
          className="messages"
          aria-live="polite"
          aria-label="Conversation"
        >
          {messages.length === 0 ? (
            <div className="empty-state">
              <h2>What would help right now?</h2>
              <p>
                Choose a prompt, adjust it if you want, then send.
              </p>

              <div
                className="prompt-tabs"
                role="tablist"
                aria-label="Prompt categories"
              >
                {starterPrompts.map((promptGroup) => (
                  <button
                    key={promptGroup.category}
                    type="button"
                    role="tab"
                    className={
                      activePromptCategory === promptGroup.category
                        ? "active"
                        : undefined
                    }
                    aria-selected={
                      activePromptCategory === promptGroup.category
                    }
                    onClick={() =>
                      setActivePromptCategory(promptGroup.category)
                    }
                  >
                    {promptGroup.category}
                  </button>
                ))}
              </div>

              <div className="prompt-grid">
                {activePromptGroup.prompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    className="prompt-button"
                    onClick={() => usePrompt(prompt)}
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
              <p>
                Checking safety, drafting a response, and saving the turn...
              </p>
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

        {/* Composer owns the current session draft and submit shortcut. */}
        <form className="composer" onSubmit={handleSubmit}>
          <label htmlFor="message">Your message</label>

          <textarea
            ref={inputRef}
            id="message"
            value={draft}
            onChange={(event) => updateDraft(event.target.value)}
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
