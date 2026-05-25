import { cn } from "@/lib/utils";
import type { InterviewChatMessage } from "@/lib/interview-chat";
import { MarkdownMessage } from "./markdown-message";
import { TypingIndicator } from "./typing-indicator";

type MessageBubbleProps = {
  message: InterviewChatMessage;
  isPending?: boolean;
};

/** 渲染单条聊天消息，按角色区分面试官与候选人的视觉样式。 */
export function MessageBubble({ message, isPending = false }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex animate-in fade-in slide-in-from-bottom-1 duration-300",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div className={cn("max-w-[85%]", isUser && "max-w-[72%]")}>
        <div
          className={cn(
            "whitespace-pre-wrap px-4 py-3 text-sm leading-relaxed shadow-sm",
            isUser
              ? "rounded-[14px_14px_3px_14px] bg-gradient-to-br from-[#534AB7] to-[#7c3aed] text-white shadow-[#534AB7]/10"
              : "rounded-[14px_14px_14px_3px] border border-black/10 bg-[#f7f6f2] text-zinc-900 dark:border-white/10 dark:bg-[#252523] dark:text-zinc-100",
          )}
        >
          {isPending && !message.content ? (
            <TypingIndicator />
          ) : (
            <MarkdownMessage content={message.content} isUser={isUser} />
          )}
        </div>
      </div>
    </div>
  );
}
