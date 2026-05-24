"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { streamInterviewChat, type InterviewChatMessage } from "@/lib/interview-chat";
import { MessageBubble } from "./message-bubble";
import { ChatInput } from "./chat-input";

/** 面试房间的单面试官流式聊天主体。 */
export function InterviewChat() {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<InterviewChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const assistantIndexRef = useRef<number | null>(null);
  const deltaBufferRef = useRef("");
  const frameRef = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

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
  }, [messages]);

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

  async function handleSend(content: string) {
    if (!content || isStreaming) return;

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
      const token = await getToken();
      if (!token) {
        throw new Error("登录状态已失效，请重新登录后再试");
      }

      await streamInterviewChat({
        token,
        messages: [...messages, userMessage],
        signal: abortController.signal,
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
        <header className="flex h-14 shrink-0 items-center border-b border-black/10 px-5 dark:border-white/10">
          <h1 className="bg-gradient-to-br from-[#534AB7] to-rose-600 bg-clip-text text-sm font-bold text-transparent">
            AI 模拟面试舱 · Agent Cabin
          </h1>
        </header>

        <div className="interview-chat-scroll flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-5 py-5">
          {messages.map((message, index) => (
            <MessageBubble
              // 当前阶段没有服务端消息 ID，顺序列表只追加或替换末尾 assistant 内容。
              key={`${message.role}-${index}`}
              message={message}
              isPending={isStreaming && index === messages.length - 1}
            />
          ))}
          <div ref={messagesEndRef} />
        </div>

        <ChatInput onSend={handleSend} isStreaming={isStreaming} />
      </div>
    </section>
  );
}

