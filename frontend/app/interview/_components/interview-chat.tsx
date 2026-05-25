"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import {
  streamInterviewChat,
  resetInterviewSession,
  type InterviewChatMessage,
  type InterviewProgressState,
  type InterviewReport,
} from "@/lib/interview-chat";
import { MessageBubble } from "./message-bubble";
import { ChatInput } from "./chat-input";
import { ReportCard } from "./report-card";
import { Button } from "@/components/ui/button";
import { Copy, Check } from "lucide-react";

function buildOpeningMessage(
  context: { target_role?: string; user_background?: string } | null,
): string {
  if (context?.target_role) {
    const bg = context.user_background
      ? `背景：${context.user_background.slice(0, 40)}。`
      : "";
    return `好，今天练「${context.target_role}」。${bg}准备好了发消息开始。`;
  }
  return "你好！在开始之前，请告诉我你想练习的面试岗位、公司，或者你想练习的具体项目背景与技术主题？（例如：AI Agent 工程师，或者分布式系统的架构设计）";
}

const INITIAL_PROGRESS: InterviewProgressState = {
  stage: "opening",
  question_count: 0,
  total_questions: 5,
};

const DEV_AUTH_BYPASS_TOKEN = "dev-auth-bypass-token";
const isDevAuthBypassEnabled = process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "1";

/** 面试房间的单面试官流式聊天主体。 */
export function InterviewChat() {
  const { isLoaded, isSignedIn, getToken } = useAuth();

  // 1. 在组件顶层读取一次上下文，供初始消息和首次 reset 使用
  const initialContextRef = useRef<{ target_role?: string; user_background?: string } | null>(null);
  const [messages, setMessages] = useState<InterviewChatMessage[]>(() => {
    if (typeof window === "undefined") return [{ role: "assistant", content: buildOpeningMessage(null) }];
    
    const raw = sessionStorage.getItem("interview_context");
    if (raw) {
      sessionStorage.removeItem("interview_context");
      try {
        const ctx = JSON.parse(raw);
        initialContextRef.current = ctx;
        return [{ role: "assistant", content: buildOpeningMessage(ctx) }];
      } catch {
        return [{ role: "assistant", content: buildOpeningMessage(null) }];
      }
    }
    return [{ role: "assistant", content: buildOpeningMessage(null) }];
  });

  const [progress, setProgress] = useState<InterviewProgressState>(INITIAL_PROGRESS);
  const [isStreaming, setIsStreaming] = useState(false);
  const [report, setReport] = useState<InterviewReport | null>(null);
  const [copied, setCopied] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const assistantIndexRef = useRef<number | null>(null);
  const deltaBufferRef = useRef("");
  const frameRef = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const hasResetRef = useRef(false);
  // 防止 reset 完成前用户提前发消息重用旧 session
  const isResettingRef = useRef(false);

  // 页面加载时 abandon 旧 session，确保每次进入都是全新一轮
  useEffect(() => {
    if (!isLoaded || (!isSignedIn && !isDevAuthBypassEnabled) || hasResetRef.current) return;

    hasResetRef.current = true;
    isResettingRef.current = true;
    getInterviewToken({ getToken, skipCache: true })
      .then(async (token) => {
        if (token) {
          await resetInterviewSession({ 
            token, 
            target_role: initialContextRef.current?.target_role,
            user_background: initialContextRef.current?.user_background,
          });
        }
      })
      .finally(() => {
        isResettingRef.current = false;
        // 首次 reset 后清空 ref，后续 handleNewRound 不再携带旧上下文
        initialContextRef.current = null;
      });
  }, [isLoaded, isSignedIn, getToken]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages, report]);

  function flushBufferedDelta() {
    const text = deltaBufferRef.current;
    const assistantIndex = assistantIndexRef.current;
    if (!text || assistantIndex === null) return;

    deltaBufferRef.current = "";
    setMessages((current) =>
      current.map((message, index) =>
        index === assistantIndex
          ? { ...message, content: `${message.content}${text}` }
          : message,
      ),
    );
  }

  function scheduleDeltaFlush() {
    if (frameRef.current !== null) return;

    frameRef.current = window.requestAnimationFrame(() => {
      frameRef.current = null;
      flushBufferedDelta();
    });
  }

  function discardBufferedDelta() {
    deltaBufferRef.current = "";
    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
  }

  function handleNewRound() {
    abortRef.current?.abort();
    discardBufferedDelta();
    setMessages([{ role: "assistant", content: buildOpeningMessage(null) }]);
    setProgress(INITIAL_PROGRESS);
    setReport(null);
    isResettingRef.current = true;
    getInterviewToken({ getToken })
      .then(async (token) => {
        if (token) await resetInterviewSession({ token });
      })
      .finally(() => {
        isResettingRef.current = false;
      });
  }

  async function handleCopyChat() {
    if (messages.length === 0) return;

    const chatText = messages
      .map((msg) => {
        const roleName = msg.role === "user" ? "求职者" : "面试官";
        return `【${roleName}】：${msg.content}`;
      })
      .join("\n\n");

    try {
      await navigator.clipboard.writeText(chatText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy chat: ", err);
    }
  }

  async function handleSend(content: string) {
    if (!content || isStreaming || isResettingRef.current) return;

    abortRef.current?.abort();
    const abortController = new AbortController();
    abortRef.current = abortController;

    const userMessage: InterviewChatMessage = { role: "user", content };
    const assistantIndex = messages.length + 1;
    const nextMessages = [...messages, userMessage, { role: "assistant" as const, content: "" }];

    assistantIndexRef.current = assistantIndex;
    discardBufferedDelta();
    setMessages(nextMessages);
    setIsStreaming(true);

    try {
      const token = await getInterviewToken({ getToken });
      if (!token) {
        throw new Error("登录状态已失效，请重新登录后再试");
      }

      await streamInterviewChat({
        token,
        message: content,
        signal: abortController.signal,
        onState: setProgress,
        onReport: setReport,
        onDelta: (text) => {
          deltaBufferRef.current += text;
          scheduleDeltaFlush();
        },
      });
      flushBufferedDelta();
    } catch (error) {
      if (abortController.signal.aborted) return;

      discardBufferedDelta();
      const message = error instanceof Error ? error.message : "AI 暂时无法响应，请稍后重试";
      setMessages((current) =>
        current.map((item, index) =>
          index === assistantIndex ? { ...item, content: message } : item,
        ),
      );
    } finally {
      if (!abortController.signal.aborted) {
        setIsStreaming(false);
      }
      assistantIndexRef.current = null;
    }
  }

  return (
    <section className="relative mx-auto flex h-[calc(100dvh-132px)] min-h-0 w-full max-w-5xl overflow-hidden rounded-2xl border border-black/10 bg-white shadow-lg shadow-black/5 dark:border-white/10 dark:bg-[#1c1c1a]">
      <div
        className="pointer-events-none absolute right-[5%] top-[18%] z-0 h-[350px] w-[350px] rounded-full bg-[radial-gradient(circle,rgba(83,74,183,0.08)_0%,rgba(244,63,94,0.04)_50%,transparent_100%)] blur-3xl"
        aria-hidden="true"
      />

      <div className="relative z-10 flex min-h-0 w-full flex-col">
        <header className="flex min-h-14 shrink-0 flex-wrap items-center justify-between gap-3 border-b border-black/10 px-5 py-3 dark:border-white/10">
          <div>
            <h1 className="bg-gradient-to-br from-[#534AB7] to-rose-600 bg-clip-text text-sm font-bold text-transparent">
              AI 模拟面试舱 · Agent Cabin
            </h1>
            <p className="mt-1 text-xs text-black/45 dark:text-white/45">
              {formatStageLabel(progress.stage)}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopyChat}
              disabled={messages.length === 0}
              className="gap-1.5 border-black/10 text-xs font-medium hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/5 disabled:pointer-events-none disabled:opacity-50"
              title="复制当前全部会话内容"
            >
              {copied ? (
                <>
                  <Check className="size-3.5 text-green-600 dark:text-green-500" />
                  <span>已复制</span>
                </>
              ) : (
                <>
                  <Copy className="size-3.5 text-black/60 dark:text-white/60" />
                  <span>复制会话</span>
                </>
              )}
            </Button>
            <InterviewProgress progress={progress} />
          </div>
        </header>

        <div className="interview-chat-scroll flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-5 py-5">
          {messages.map((message, index) => (
            <MessageBubble
              key={`${message.role}-${index}`}
              message={message}
              isPending={isStreaming && index === messages.length - 1}
            />
          ))}
          {report && (
            <>
              <div className="flex items-center gap-3 py-1" role="separator" aria-label="面试结束">
                <div className="flex-1 border-t border-black/10 dark:border-white/10" />
                <span className="shrink-0 text-xs text-black/35 dark:text-white/35">面试结束 · 评估报告</span>
                <div className="flex-1 border-t border-black/10 dark:border-white/10" />
              </div>
              <ReportCard report={report} />
            </>
          )}
          <div ref={messagesEndRef} />
        </div>

        {progress.stage === "closing" && (
          <div className="shrink-0 px-5 pb-3">
            <Button variant="outline" onClick={handleNewRound}>
              开始新一轮面试
            </Button>
          </div>
        )}
        <ChatInput onSend={handleSend} isStreaming={isStreaming} />
      </div>
    </section>
  );
}

async function getInterviewToken({
  getToken,
  skipCache,
}: {
  getToken: ReturnType<typeof useAuth>["getToken"];
  skipCache?: boolean;
}) {
  if (isDevAuthBypassEnabled) return DEV_AUTH_BYPASS_TOKEN;
  return getToken(skipCache ? { skipCache: true } : undefined);
}

function InterviewProgress({ progress }: { progress: InterviewProgressState }) {
  const total = Math.max(progress.total_questions, 1);
  const current = Math.min(Math.max(progress.question_count, 0), total);
  const percent = progress.stage === "closing" ? 100 : Math.round((current / total) * 100);

  return (
    <div className="flex min-w-[168px] flex-col gap-1.5" aria-label="面试进度">
      <div className="flex items-center justify-between text-xs font-medium text-black/60 dark:text-white/60">
        <span>{progress.stage === "opening" ? "准备中" : `第 ${current}/${total} 题`}</span>
        <span>{percent}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
        <div
          className="h-full rounded-full bg-[#534AB7] transition-[width] duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function formatStageLabel(stage: InterviewProgressState["stage"]) {
  if (stage === "opening") return "开场信息收集中";
  if (stage === "closing") return "本轮面试已结束";
  return "正式面试进行中";
}
