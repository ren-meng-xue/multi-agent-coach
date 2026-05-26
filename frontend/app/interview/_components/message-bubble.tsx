import { cn } from "@/lib/utils";
import type { InterviewChatTextMessage, InterviewTurnTraceMessage } from "@/lib/interview-chat";
import { MarkdownMessage } from "./markdown-message";
import { TypingIndicator } from "./typing-indicator";
import { TurnTraceCard } from "./turn-trace-card";

type MessageBubbleProps = {
  message: InterviewChatTextMessage;
  isPending?: boolean;
  trace?: InterviewTurnTraceMessage;
};

/** 渲染单条聊天消息，按角色区分面试官与候选人的视觉样式，支持内嵌 Trace 面板思考抽屉。 */
export function MessageBubble({ message, isPending = false, trace }: MessageBubbleProps) {
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

          {/* AI 消息底部内嵌多 Agent 协作思考过程，以折叠抽屉形式融合呈现 */}
          {!isUser && trace && (
            <div className="mt-3 border-t border-dashed border-black/[0.06] pt-2.5 dark:border-white/[0.06] animate-in fade-in slide-in-from-top-1 duration-300">
              <TurnTraceCard
                status={trace.payload.status}
                nodes={trace.payload.nodes}
                turnIndex={trace.payload.turnIndex}
                summaryScore={trace.payload.summaryScore}
                isOpening={trace.payload.isOpening}
                isEmbedded={true}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
