import {
  FormEvent,
  KeyboardEvent,
  useMemo,
  useRef,
  useState,
} from "react";

import { sendChatMessage } from "./api";
import type {
  ChatMessage,
  RiskLevel,
} from "./types";

interface DisplayMessage extends ChatMessage {
  id: string;
  riskLevel?: RiskLevel;
}

const starterPrompts = [
  "I feel overwhelmed and need a grounding exercise.",
  "Help me understand why stress affects my sleep.",
  "How can I communicate a boundary calmly?",
];

function createId(): string {
  return crypto.randomUUID();
}

export default function App() {
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

  async function submitMessage(rawMessage: string) {
    const message = rawMessage.trim();

    if (!message || isSending) {
      return;
    }

    const previousHistory = history;

    setMessages((current) => [
      ...current,
      {
        id: createId(),
        role: "user",
        content: message,
      },
    ]);
    setDraft("");
    setError(null);
    setIsSending(true);

    try {
      const response = await sendChatMessage(
        message,
        previousHistory,
      );

      setMessages((current) => [
        ...current,
        {
          id: createId(),
          role: "assistant",
          content: response.reply,
          riskLevel: response.risk_level,
        },
      ]);
    } catch (caughtError) {
      const messageText =
        caughtError instanceof Error
          ? caughtError.message
          : "An unexpected error occurred.";

      setError(messageText);
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
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

  function clearConversation() {
    setMessages([]);
    setError(null);
    setDraft("");
    inputRef.current?.focus();
  }

  return (
    <main className="app-shell">
      <section className="chat-card">
        <header className="app-header">
          <div>
            <p className="eyebrow">Safety-aware AI demo</p>
            <h1>Emotional Support Guide</h1>
            <p className="subtitle">
              General emotional support and psychoeducation.
            </p>
          </div>

          <button
            className="secondary-button"
            type="button"
            onClick={clearConversation}
            disabled={messages.length === 0 || isSending}
          >
            Clear chat
          </button>
        </header>

        <div className="notice" role="note">
          This assistant is not a therapist, diagnostic tool, or
          emergency service. Do not share identifying or highly
          sensitive information in this development demo.
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
            messages.map((message) => (
              <article
                key={message.id}
                className={`message ${message.role}`}
              >
                <div className="message-heading">
                  <strong>
                    {message.role === "user" ? "You" : "Guide"}
                  </strong>

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

                <p>{message.content}</p>
              </article>
            ))
          )}

          {isSending && (
            <article className="message assistant loading-message">
              <strong>Guide</strong>
              <p>Thinking carefully…</p>
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
            placeholder="Write what is happening or ask for a coping strategy…"
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
              {isSending ? "Sending…" : "Send"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}
