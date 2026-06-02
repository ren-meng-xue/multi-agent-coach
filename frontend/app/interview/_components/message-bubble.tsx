import { memo } from "react";
import { cn } from "@/lib/utils";
import type {
  InterviewChatTextMessage,
  InterviewTurnTraceMessage,
} from "@/lib/interview-chat";
import { MarkdownMessage } from "./markdown-message";
import { TypingIndicator } from "./typing-indicator";
import { TurnTraceCard } from "./turn-trace-card";

type MessageBubbleProps = {
  message: InterviewChatTextMessage;
  isPending?: boolean;
  trace?: InterviewTurnTraceMessage;
};

/** 渲染单条聊天消息，按角色区分面试官与候选人的视觉样式。 */
export const MessageBubble = memo(function MessageBubble({
  message,
  isPending = false,
  trace,
}: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex animate-in fade-in slide-in-from-bottom-1 duration-300",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div className={cn(isUser ? "max-w-[72%]" : "max-w-[95%]")}>
        <div
            className={cn(
            "whitespace-pre-wrap text-base leading-relaxed transition-all duration-300",
            isUser
              ? "rounded-[18px_18px_4px_18px] bg-gradient-to-br from-[#534AB7] to-[#7c3aed] px-6 py-4 text-white shadow-sm shadow-[#534AB7]/10"
              : "rounded-[20px_20px_20px_6px] bg-[#F7F8FC] border border-slate-100/90 dark:bg-zinc-900/40 dark:border-zinc-800/50 px-6 py-5 text-zinc-800 dark:text-zinc-200 shadow-[0_4px_20px_-4px_rgba(83,74,183,0.02)]",
          )}
        >
          {isPending && !message.content && !trace ? (
            <TypingIndicator />
          ) : (
            message.content && (
              <MarkdownMessage content={message.content} isUser={isUser} />
            )
          )}

          {!isUser && trace && (
            <TurnTraceCard
              status={trace.payload.status}
              nodes={trace.payload.nodes}
              turnIndex={trace.payload.turnIndex}
              summaryScore={trace.payload.summaryScore}
              isOpening={trace.payload.isOpening}
              isEmbedded={true}
              hasContent={!!message.content}
            />
          )}

          {isPending && message.content && (
            <div className="mt-1 flex justify-start">
              <span className="size-1 animate-pulse rounded-full bg-black/20 dark:bg-white/20" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
});
