import { FormEvent, useEffect, useState } from "react";

import type { SavedConversationSummary } from "../types";
import { formatSavedDate } from "../chatHelpers";

// Shared props keep the desktop sidebar and mobile saved-chat panel in sync.
// Both views use the same filters, actions, and active chat state.
interface SavedChatsProps {
  chats: SavedConversationSummary[];
  activeSessionId: string;
  savedChatsCount: number;
  savedChatsLimit: number;
  search: string;
  onSearchChange: (value: string) => void;
  filter: "all" | "pinned" | "expiring";
  onFilterChange: (value: "all" | "pinned" | "expiring") => void;
  pinnedChatIds: string[];
  onTogglePinnedChat: (sessionId: string) => void;
  onRenameChat: (sessionId: string, nextTitle: string) => void;
  onOpenChat: (sessionId: string) => void;
  onDeleteChat: (sessionId: string) => void;
  onStartNewChat: () => void;
  isLoading: boolean;
  isSending: boolean;
}

interface SavedChatsPanelProps extends SavedChatsProps {
  onClose: () => void;
}

// Persistent desktop navigation shown beside the main chat card.
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

      <SavedChatFilters
        value={props.filter}
        onChange={props.onFilterChange}
        pinnedCount={props.pinnedChatIds.length}
      />

      <SavedChatList
        variant="sidebar"
        chats={props.chats}
        activeSessionId={props.activeSessionId}
        search={props.search}
        filter={props.filter}
        pinnedChatIds={props.pinnedChatIds}
        isLoading={props.isLoading}
        onOpenChat={props.onOpenChat}
        onTogglePinnedChat={props.onTogglePinnedChat}
        onRenameChat={props.onRenameChat}
        onDeleteChat={props.onDeleteChat}
      />
    </aside>
  );
}

// Mobile/in-page saved-chat browser. It reuses the same list building blocks as
// the desktop sidebar, but adds a close button and wider item layout.
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

      <SavedChatFilters
        value={props.filter}
        onChange={props.onFilterChange}
        pinnedCount={props.pinnedChatIds.length}
      />

      <SavedChatList
        variant="panel"
        chats={props.chats}
        activeSessionId={props.activeSessionId}
        search={props.search}
        filter={props.filter}
        pinnedChatIds={props.pinnedChatIds}
        isLoading={props.isLoading}
        onOpenChat={props.onOpenChat}
        onTogglePinnedChat={props.onTogglePinnedChat}
        onRenameChat={props.onRenameChat}
        onDeleteChat={props.onDeleteChat}
      />
    </section>
  );
}

// Search is controlled by App.tsx so sidebar and panel stay synchronized.
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

// Filter buttons are purely client-side; App.tsx does the actual filtering.
function SavedChatFilters({
  value,
  onChange,
  pinnedCount,
}: {
  value: "all" | "pinned" | "expiring";
  onChange: (value: "all" | "pinned" | "expiring") => void;
  pinnedCount: number;
}) {
  const filters: Array<{
    label: string;
    value: "all" | "pinned" | "expiring";
  }> = [
    { label: "All", value: "all" },
    { label: `Pinned ${pinnedCount}`, value: "pinned" },
    { label: "Expiring", value: "expiring" },
  ];

  return (
    <div className="saved-chat-filters" aria-label="Saved chat filters">
      {filters.map((filter) => (
        <button
          key={filter.value}
          type="button"
          className={value === filter.value ? "active" : undefined}
          aria-pressed={value === filter.value}
          onClick={() => onChange(filter.value)}
        >
          {filter.label}
        </button>
      ))}
    </div>
  );
}

// Handles loading/empty/list states before rendering individual chat cards.
function SavedChatList({
  variant,
  chats,
  activeSessionId,
  search,
  filter,
  pinnedChatIds,
  isLoading,
  onOpenChat,
  onTogglePinnedChat,
  onRenameChat,
  onDeleteChat,
}: {
  variant: "sidebar" | "panel";
  chats: SavedConversationSummary[];
  activeSessionId: string;
  search: string;
  filter: "all" | "pinned" | "expiring";
  pinnedChatIds: string[];
  isLoading: boolean;
  onOpenChat: (sessionId: string) => void;
  onTogglePinnedChat: (sessionId: string) => void;
  onRenameChat: (sessionId: string, nextTitle: string) => void;
  onDeleteChat: (sessionId: string) => void;
}) {
  const emptyMessage = getEmptyMessage(search, filter);

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
          isPinned={pinnedChatIds.includes(chat.session_id)}
          variant={variant}
          onOpenChat={onOpenChat}
          onTogglePinnedChat={onTogglePinnedChat}
          onRenameChat={onRenameChat}
          onDeleteChat={onDeleteChat}
        />
      ))}
    </div>
  );
}

// The empty message changes based on why the list is empty.
function getEmptyMessage(
  search: string,
  filter: "all" | "pinned" | "expiring",
) {
  if (search) {
    return "No saved chats match your search.";
  }

  if (filter === "pinned") {
    return "Pinned chats will appear here.";
  }

  if (filter === "expiring") {
    return "No saved chats are expiring soon.";
  }

  return "Saved chats will appear here after a reply is stored.";
}

// One saved chat row/card. It owns only temporary inline rename state; all
// durable actions are handed back up to App.tsx.
function SavedChatItem({
  chat,
  isActive,
  isPinned,
  variant,
  onOpenChat,
  onTogglePinnedChat,
  onRenameChat,
  onDeleteChat,
}: {
  chat: SavedConversationSummary;
  isActive: boolean;
  isPinned: boolean;
  variant: "sidebar" | "panel";
  onOpenChat: (sessionId: string) => void;
  onTogglePinnedChat: (sessionId: string) => void;
  onRenameChat: (sessionId: string, nextTitle: string) => void;
  onDeleteChat: (sessionId: string) => void;
}) {
  const [isRenaming, setIsRenaming] = useState(false);
  const [draftTitle, setDraftTitle] = useState(chat.title);
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

  // If the backend refresh changes the title, reset the local rename draft.
  useEffect(() => {
    setDraftTitle(chat.title);
  }, [chat.title]);

  function submitRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const cleanedTitle = draftTitle.trim();
    if (cleanedTitle && cleanedTitle !== chat.title) {
      onRenameChat(chat.session_id, cleanedTitle);
    }

    setIsRenaming(false);
  }

  return (
    <article className={articleClassName}>
      {isRenaming ? (
        <form className="saved-chat-rename-form" onSubmit={submitRename}>
          <label>
            Rename chat
            <input
              value={draftTitle}
              onChange={(event) => setDraftTitle(event.target.value)}
              maxLength={80}
              autoFocus
            />
          </label>
          <div>
            <button type="submit" className="saved-chat-pin">
              Save
            </button>
            <button
              type="button"
              className="saved-chat-rename"
              onClick={() => {
                setDraftTitle(chat.title);
                setIsRenaming(false);
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          className={openClassName}
          onClick={() => onOpenChat(chat.session_id)}
        >
          <span className="saved-chat-title-row">
            <span className="saved-chat-title">{chat.title}</span>
            {isPinned && (
              <span className="saved-chat-pin-label">Pinned</span>
            )}
          </span>
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
      )}

      <div className="saved-chat-actions">
        <button
          type="button"
          className="saved-chat-pin"
          onClick={() => onTogglePinnedChat(chat.session_id)}
          aria-pressed={isPinned}
          aria-label={
            isPinned
              ? `Unpin saved chat: ${chat.title}`
              : `Pin saved chat: ${chat.title}`
          }
        >
          {isPinned ? "Unpin" : "Pin"}
        </button>

        <button
          type="button"
          className="saved-chat-rename"
          onClick={() => setIsRenaming(true)}
          aria-label={`Rename saved chat: ${chat.title}`}
        >
          Rename
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
      </div>
    </article>
  );
}
