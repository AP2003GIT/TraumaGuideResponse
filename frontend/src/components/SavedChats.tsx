import type { SavedConversationSummary } from "../types";
import { formatSavedDate } from "../chatHelpers";

interface SavedChatsProps {
  chats: SavedConversationSummary[];
  activeSessionId: string;
  savedChatsCount: number;
  savedChatsLimit: number;
  search: string;
  onSearchChange: (value: string) => void;
  onOpenChat: (sessionId: string) => void;
  onDeleteChat: (sessionId: string) => void;
  onStartNewChat: () => void;
  isLoading: boolean;
  isSending: boolean;
}

interface SavedChatsPanelProps extends SavedChatsProps {
  onClose: () => void;
}

export function SavedChatsSidebar(props: SavedChatsProps) {
  return (
    <aside className="saved-sidebar" aria-labelledby="sidebar-heading">
      <div className="saved-sidebar-header">
        <div>
          <h2 id="sidebar-heading">Saved chats</h2>
          <p>
            {props.savedChatsCount}/{props.savedChatsLimit} saved
          </p>
        </div>

        <button
          className="primary-button compact-button"
          type="button"
          onClick={props.onStartNewChat}
          disabled={props.isSending}
        >
          New
        </button>
      </div>

      <SearchField
        value={props.search}
        onChange={props.onSearchChange}
      />

      <SavedChatList
        variant="sidebar"
        chats={props.chats}
        activeSessionId={props.activeSessionId}
        search={props.search}
        isLoading={props.isLoading}
        onOpenChat={props.onOpenChat}
        onDeleteChat={props.onDeleteChat}
      />
    </aside>
  );
}

export function SavedChatsPanel({
  onClose,
  ...props
}: SavedChatsPanelProps) {
  return (
    <section
      id="saved-chats-panel"
      className="saved-chats-panel"
      aria-labelledby="saved-chats-heading"
    >
      <div className="saved-chats-header">
        <div>
          <h2 id="saved-chats-heading">Saved chats</h2>
          <p>
            {props.savedChatsCount}/{props.savedChatsLimit} saved
          </p>
        </div>

        <div className="saved-chats-actions">
          <button
            className="secondary-button compact-button"
            type="button"
            onClick={props.onStartNewChat}
            disabled={props.isSending}
          >
            New chat
          </button>

          <button
            className="secondary-button compact-button"
            type="button"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>

      <SearchField
        value={props.search}
        onChange={props.onSearchChange}
        className="panel-search"
      />

      <SavedChatList
        variant="panel"
        chats={props.chats}
        activeSessionId={props.activeSessionId}
        search={props.search}
        isLoading={props.isLoading}
        onOpenChat={props.onOpenChat}
        onDeleteChat={props.onDeleteChat}
      />
    </section>
  );
}

function SearchField({
  value,
  onChange,
  className = "",
}: {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <label className={`sidebar-search ${className}`.trim()}>
      Search chats
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Search saved chats"
      />
    </label>
  );
}

function SavedChatList({
  variant,
  chats,
  activeSessionId,
  search,
  isLoading,
  onOpenChat,
  onDeleteChat,
}: {
  variant: "sidebar" | "panel";
  chats: SavedConversationSummary[];
  activeSessionId: string;
  search: string;
  isLoading: boolean;
  onOpenChat: (sessionId: string) => void;
  onDeleteChat: (sessionId: string) => void;
}) {
  const emptyMessage = search
    ? "No saved chats match your search."
    : "Saved chats will appear here after a reply is stored.";

  if (isLoading) {
    return <div className="saved-chats-empty">Loading saved chats...</div>;
  }

  if (chats.length === 0) {
    return <div className="saved-chats-empty">{emptyMessage}</div>;
  }

  const listClassName =
    variant === "sidebar" ? "sidebar-list" : "saved-chat-list";

  return (
    <div className={listClassName} aria-label="Saved chats">
      {chats.map((chat) => (
        <SavedChatItem
          key={chat.session_id}
          chat={chat}
          isActive={chat.session_id === activeSessionId}
          variant={variant}
          onOpenChat={onOpenChat}
          onDeleteChat={onDeleteChat}
        />
      ))}
    </div>
  );
}

function SavedChatItem({
  chat,
  isActive,
  variant,
  onOpenChat,
  onDeleteChat,
}: {
  chat: SavedConversationSummary;
  isActive: boolean;
  variant: "sidebar" | "panel";
  onOpenChat: (sessionId: string) => void;
  onDeleteChat: (sessionId: string) => void;
}) {
  const articleClassName =
    variant === "sidebar"
      ? isActive
        ? "sidebar-chat active"
        : "sidebar-chat"
      : isActive
        ? "saved-chat-item active"
        : "saved-chat-item";
  const openClassName =
    variant === "sidebar" ? "sidebar-chat-open" : "saved-chat-open";

  return (
    <article className={articleClassName}>
      <button
        type="button"
        className={openClassName}
        onClick={() => onOpenChat(chat.session_id)}
      >
        <span className="saved-chat-title">{chat.title}</span>
        <span className="saved-chat-preview">
          {chat.last_message_preview}
        </span>
        <span className="saved-chat-meta">
          {variant === "sidebar"
            ? `${chat.message_count} messages - ${formatSavedDate(
                chat.updated_at,
              )}`
            : `${chat.message_count} messages - Updated ${formatSavedDate(
                chat.updated_at,
              )} - Expires ${formatSavedDate(chat.expires_at)}`}
        </span>
      </button>

      <button
        type="button"
        className={
          variant === "sidebar"
            ? "saved-chat-delete icon-delete"
            : "saved-chat-delete"
        }
        onClick={() => onDeleteChat(chat.session_id)}
        aria-label={`Delete saved chat: ${chat.title}`}
      >
        Delete
      </button>
    </article>
  );
}
