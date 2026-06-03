import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type MarkdownMessageProps = {
  content: string;
  isUser: boolean;
  suffix?: ReactNode;
};

type Block =
  | { type: "paragraph"; lines: string[] }
  | { type: "unordered-list"; items: string[] }
  | { type: "ordered-list"; items: string[] }
  | { type: "blockquote"; lines: string[] }
  | { type: "todo-list"; items: { checked: boolean; text: string }[] }
  | { type: "code"; language: string; content: string }
  | { type: "heading"; level: number; text: string }
  | { type: "thematic-break" };

/** 渲染面试回复常见 Markdown 子集，不使用 HTML 注入，避免模型输出变成可执行内容。 */
export function MarkdownMessage({
  content,
  isUser,
  suffix,
}: MarkdownMessageProps) {
  const blocks = parseMarkdownBlocks(content);

  const lastBlock = blocks[blocks.length - 1];
  const supportsInlineSuffix =
    lastBlock &&
    [
      "paragraph",
      "unordered-list",
      "ordered-list",
      "todo-list",
      "blockquote",
    ].includes(lastBlock.type);

  return (
    <div className="space-y-3">
      {blocks.map((block, index) => {
        const isLastBlock = index === blocks.length - 1;
        const rendered = renderBlock(block, index, isUser, isLastBlock, suffix);
        if (isLastBlock && !supportsInlineSuffix && suffix) {
          return (
            <div key={index} className="space-y-3">
              {rendered}
              <div className="mt-1 flex justify-end">{suffix}</div>
            </div>
          );
        }
        return rendered;
      })}
    </div>
  );
}

function parseMarkdownBlocks(content: string): Block[] {
  const lines = content.split(/\r?\n/);
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let listType:
    | "unordered-list"
    | "ordered-list"
    | "todo-list"
    | "blockquote"
    | null = null;
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
      if (listType === "blockquote") {
        blocks.push({ type: "blockquote", lines: listItems });
      } else if (listType === "todo-list") {
        const todoItems = listItems.map((item) => {
          const match = item.match(/^\[([ xX])\]\s*(.+)$/);
          return {
            checked: match ? match[1].toLowerCase() === "x" : false,
            text: match ? match[2] : item,
          };
        });
        blocks.push({ type: "todo-list", items: todoItems });
      } else {
        blocks.push({ type: listType, items: listItems });
      }
      listItems = [];
      listType = null;
    }
  }

  function flushCode() {
    blocks.push({
      type: "code",
      language: codeLanguage,
      content: codeLines.join("\n"),
    });
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

    // 1. 匹配分割线 (--- 或 *** 或 ___)
    const hrMatch = line.match(/^\s*([-*_])\1{2,}\s*$/);
    if (hrMatch) {
      flushParagraph();
      flushList();
      blocks.push({ type: "thematic-break" });
      continue;
    }

    // 2. 匹配标题 (### 标题 或 ## 标题 或 # 标题)
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      blocks.push({
        type: "heading",
        level: headingMatch[1].length,
        text: headingMatch[2],
      });
      continue;
    }

    // 3. 匹配 blockquote (▎, ▌, ▍, |, > 等前缀)
    const quoteMatch = line.match(/^\s*[▎▌▍|>\u2588-\u258f]\s*(.*)$/);
    if (quoteMatch) {
      flushParagraph();
      if (listType !== "blockquote") {
        flushList();
        listType = "blockquote";
      }
      listItems.push(quoteMatch[1]);
      continue;
    }

    // 2. 无序列表（含 Todo List 判断）
    const unordered = line.match(/^\s*[-*]\s+(.+)$/);
    if (unordered) {
      flushParagraph();
      const todoMatch = unordered[1].match(/^\[([ xX])\]\s*(.+)$/);
      if (todoMatch) {
        if (listType !== "todo-list") {
          flushList();
          listType = "todo-list";
        }
        listItems.push(unordered[1]);
      } else {
        if (listType !== "unordered-list") {
          flushList();
          listType = "unordered-list";
        }
        listItems.push(unordered[1]);
      }
      continue;
    }

    // 3. 有序列表
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

function smartJoinParagraphLines(lines: string[]): string {
  let result = "";
  for (let i = 0; i < lines.length; i++) {
    const current = lines[i];
    const next = lines[i + 1];

    result += current;
    if (next !== undefined) {
      const trimmedCurrent = current.trim();
      const trimmedNext = next.trim();

      if (trimmedCurrent === "" || trimmedNext === "") {
        // 如果有任意一行是空行，说明是真正的段落分行，保留换行
        result += "\n";
      } else {
        // 如果当前行以中文或英文句号、感叹号、问号、冒号、分号、收尾括号、引号等结束，说明是故意换行，应保留换行
        const isSentenceEnd = /[。！？：；”）”〉》】\]\.\?!\:;\)"]$/.test(
          trimmedCurrent,
        );
        if (isSentenceEnd) {
          result += "\n";
        } else {
          // 两个都是非空行，且当前行不是句子结尾，说明这是一个硬折行，必须进行智能合并
          const hasChinese =
            /[\u4e00-\u9fa5]/.test(trimmedCurrent) ||
            /[\u4e00-\u9fa5]/.test(trimmedNext);
          if (hasChinese) {
            // 只要有任意一方是中文，直接拼接消除换行
          } else {
            // 纯英文或西文字符相连，用空格连接
            if (
              /[a-zA-Z0-9,\.\?!]$/.test(trimmedCurrent) &&
              /^[a-zA-Z0-9]/.test(trimmedNext)
            ) {
              result += " ";
            } else {
              // 其他符号拼接，保留紧凑
            }
          }
        }
      }
    }
  }
  return result;
}

function renderBlock(
  block: Block,
  index: number,
  isUser: boolean,
  isLastBlock?: boolean,
  suffix?: ReactNode,
): ReactNode {
  if (block.type === "heading") {
    const Tag = `h${block.level}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
    const sizeClass = {
      h1: "text-lg font-extrabold text-zinc-900 dark:text-zinc-100 mt-4 mb-2 first:mt-0",
      h2: "text-base font-bold text-zinc-900 dark:text-zinc-100 mt-3 mb-1.5 first:mt-0",
      h3: "text-sm font-semibold text-zinc-900 dark:text-zinc-100 mt-2.5 mb-1 first:mt-0",
      h4: "text-sm font-medium text-zinc-900 dark:text-zinc-100 mt-2 mb-1 first:mt-0",
      h5: "text-xs font-semibold text-zinc-900 dark:text-zinc-100 mt-2 mb-1 first:mt-0",
      h6: "text-xs font-medium text-zinc-900 dark:text-zinc-100 mt-2 mb-1 first:mt-0",
    }[Tag];

    return (
      <Tag key={index} className={cn(sizeClass, isUser && "text-white")}>
        {renderInline(block.text, isUser)}
      </Tag>
    );
  }

  if (block.type === "thematic-break") {
    return (
      <hr
        key={index}
        className={cn(
          "my-4 border-t border-black/10 dark:border-white/10",
          isUser && "border-white/20",
        )}
      />
    );
  }

  if (block.type === "paragraph") {
    const text = smartJoinParagraphLines(block.lines).replace(/\n+$/, "");
    return (
      <p key={index} className="whitespace-pre-wrap">
        {renderInline(text, isUser)}
        {isLastBlock && suffix && (
          <span
            className="inline-flex ml-2 items-center select-none align-middle"
            onClick={(e) => e.stopPropagation()}
          >
            {suffix}
          </span>
        )}
      </p>
    );
  }

  if (block.type === "blockquote") {
    const text = smartJoinParagraphLines(block.lines).replace(/\n+$/, "");
    return (
      <blockquote
        key={index}
        className={cn(
          "border-l-3 border-[#534AB7]/40 bg-zinc-100/50 dark:bg-zinc-800/30 pl-3.5 py-1.5 pr-2 my-2 rounded-r-lg text-sm leading-relaxed",
          isUser
            ? "text-white/90 border-white/40 bg-white/10"
            : "text-zinc-700 dark:text-zinc-300",
        )}
      >
        {renderInline(text, isUser)}
        {isLastBlock && suffix && (
          <span
            className="inline-flex ml-2 items-center select-none align-middle"
            onClick={(e) => e.stopPropagation()}
          >
            {suffix}
          </span>
        )}
      </blockquote>
    );
  }

  if (block.type === "todo-list") {
    return (
      <ul key={index} className="space-y-2 my-2 pl-1">
        {block.items.map((item, itemIndex) => {
          const isLastItem = itemIndex === block.items.length - 1;
          return (
            <li key={itemIndex} className="flex items-start gap-2.5 text-sm">
              <input
                type="checkbox"
                checked={item.checked}
                readOnly
                className="mt-1 size-3.5 shrink-0 rounded border-black/10 accent-[#534AB7] dark:border-white/10"
              />
              <span
                className={cn(
                  item.checked
                    ? "text-zinc-400 line-through decoration-zinc-400/50"
                    : "text-zinc-800 dark:text-zinc-200",
                )}
              >
                {renderInline(item.text, isUser)}
                {isLastBlock && isLastItem && suffix && (
                  <span
                    className="inline-flex ml-2 items-center select-none align-middle"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {suffix}
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
    );
  }

  if (block.type === "unordered-list") {
    return (
      <ul key={index} className="list-disc space-y-1 pl-5">
        {block.items.map((item, itemIndex) => {
          const isLastItem = itemIndex === block.items.length - 1;
          return (
            <li key={itemIndex}>
              {renderInline(item, isUser)}
              {isLastBlock && isLastItem && suffix && (
                <span
                  className="inline-flex ml-2 items-center select-none align-middle"
                  onClick={(e) => e.stopPropagation()}
                >
                  {suffix}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    );
  }

  if (block.type === "ordered-list") {
    return (
      <ol key={index} className="list-decimal space-y-1 pl-5">
        {block.items.map((item, itemIndex) => {
          const isLastItem = itemIndex === block.items.length - 1;
          return (
            <li key={itemIndex}>
              {renderInline(item, isUser)}
              {isLastBlock && isLastItem && suffix && (
                <span
                  className="inline-flex ml-2 items-center select-none align-middle"
                  onClick={(e) => e.stopPropagation()}
                >
                  {suffix}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    );
  }

  return (
    <pre
      key={index}
      className={cn(
        "overflow-x-auto rounded-md px-3 py-2 text-xs leading-relaxed",
        isUser
          ? "bg-black/20 text-white"
          : "bg-black/5 text-zinc-900 dark:bg-white/10 dark:text-zinc-100",
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
            isUser
              ? "bg-white/15 text-white"
              : "bg-black/5 text-zinc-900 dark:bg-white/10 dark:text-zinc-100",
          )}
        >
          {value.slice(1, -1)}
        </code>,
      );
    } else {
      nodes.push(
        <strong
          key={key}
          className={cn(
            "font-extrabold",
            isUser
              ? "text-white border-b border-white/40"
              : "text-[#534AB7] dark:text-[#9A91FB] bg-[#534AB7]/5 dark:bg-[#9A91FB]/10 px-1 py-0.5 rounded",
          )}
        >
          {value.slice(2, -2)}
        </strong>,
      );
    }

    lastIndex = match.index + value.length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.map((node, index) => <Fragment key={index}>{node}</Fragment>);
}
