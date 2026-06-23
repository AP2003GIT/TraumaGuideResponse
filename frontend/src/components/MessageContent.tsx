import type { ReactNode } from "react";

import type { Role } from "../types";

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

export function MessageContent({
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
