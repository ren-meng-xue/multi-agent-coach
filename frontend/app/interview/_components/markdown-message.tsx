import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type MarkdownMessageProps = {
  content: string;
  isUser: boolean;
};

type Block =
  | { type: "paragraph"; lines: string[] }
  | { type: "unordered-list"; items: string[] }
  | { type: "ordered-list"; items: string[] }
  | { type: "code"; language: string; content: string };

/** 渲染面试回复常见 Markdown 子集，不使用 HTML 注入，避免模型输出变成可执行内容。 */
export function MarkdownMessage({ content, isUser }: MarkdownMessageProps) {
  const blocks = parseMarkdownBlocks(content);

  return (
    <div className="space-y-3">
      {blocks.map((block, index) => renderBlock(block, index, isUser))}
    </div>
  );
}

function parseMarkdownBlocks(content: string): Block[] {
  const lines = content.split(/\r?\n/);
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let listType: "unordered-list" | "ordered-list" | null = null;
  let codeLines: string[] = [];
  let codeLanguage = "";
  let inCodeBlock = false;

  function flushParagraph() {
    if (paragraph.length) {
      blocks.push({ type: "paragraph", lines: paragraph });
      paragraph = [];
    }
  }

  function flushList() {
    if (listType && listItems.length) {
      blocks.push({ type: listType, items: listItems });
      listItems = [];
      listType = null;
    }
  }

  function flushCode() {
    blocks.push({ type: "code", language: codeLanguage, content: codeLines.join("\n") });
    codeLines = [];
    codeLanguage = "";
  }

  for (const line of lines) {
    const fence = line.match(/^```(\S*)\s*$/);
    if (fence) {
      if (inCodeBlock) {
        flushCode();
        inCodeBlock = false;
      } else {
        flushParagraph();
        flushList();
        inCodeBlock = true;
        codeLanguage = fence[1] ?? "";
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }

    const unordered = line.match(/^\s*[-*]\s+(.+)$/);
    if (unordered) {
      flushParagraph();
      if (listType !== "unordered-list") {
        flushList();
        listType = "unordered-list";
      }
      listItems.push(unordered[1]);
      continue;
    }

    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (ordered) {
      flushParagraph();
      if (listType !== "ordered-list") {
        flushList();
        listType = "ordered-list";
      }
      listItems.push(ordered[1]);
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  if (inCodeBlock) {
    paragraph.push(["```", ...codeLines].join("\n"));
  }
  flushParagraph();
  flushList();

  return blocks.length ? blocks : [{ type: "paragraph", lines: [content] }];
}

function renderBlock(block: Block, index: number, isUser: boolean): ReactNode {
  if (block.type === "paragraph") {
    return (
      <p key={index} className="whitespace-pre-wrap">
        {renderInline(block.lines.join("\n"), isUser)}
      </p>
    );
  }

  if (block.type === "unordered-list") {
    return (
      <ul key={index} className="list-disc space-y-1 pl-5">
        {block.items.map((item, itemIndex) => (
          <li key={itemIndex}>{renderInline(item, isUser)}</li>
        ))}
      </ul>
    );
  }

  if (block.type === "ordered-list") {
    return (
      <ol key={index} className="list-decimal space-y-1 pl-5">
        {block.items.map((item, itemIndex) => (
          <li key={itemIndex}>{renderInline(item, isUser)}</li>
        ))}
      </ol>
    );
  }

  return (
    <pre
      key={index}
      className={cn(
        "overflow-x-auto rounded-md px-3 py-2 text-xs leading-relaxed",
        isUser ? "bg-black/20 text-white" : "bg-black/5 text-zinc-900 dark:bg-white/10 dark:text-zinc-100",
      )}
    >
      <code data-language={block.language || undefined}>{block.content}</code>
    </pre>
  );
}

function renderInline(text: string, isUser: boolean): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    const value = match[0];
    const key = `${match.index}-${value}`;
    if (value.startsWith("`")) {
      nodes.push(
        <code
          key={key}
          className={cn(
            "rounded px-1 py-0.5 text-[0.92em]",
            isUser ? "bg-white/15 text-white" : "bg-black/5 text-zinc-900 dark:bg-white/10 dark:text-zinc-100",
          )}
        >
          {value.slice(1, -1)}
        </code>,
      );
    } else {
      nodes.push(<strong key={key}>{value.slice(2, -2)}</strong>);
    }

    lastIndex = match.index + value.length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.map((node, index) => <Fragment key={index}>{node}</Fragment>);
}
