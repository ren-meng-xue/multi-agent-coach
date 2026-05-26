"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import {
  streamInterviewChat,
  resetInterviewSession,
  startPrepareStreamFetch,
  resumePrepareStreamFetch,
  isPrepareTraceMessage,
  isTextMessage,
  isTurnTraceMessage,
  type InterviewChatMessage,
  type InterviewPrepareTracePayload,
  type InterviewProgressState,
  type InterviewReport,
} from "@/lib/interview-chat";
import { MessageBubble } from "./message-bubble";
import { ChatInput } from "./chat-input";
import { ReportCard } from "./report-card";
import { Button } from "@/components/ui/button";
import { Copy, Check } from "lucide-react";
import { PreparationCard } from "./preparation-card";
import { TurnTraceCard } from "./turn-trace-card";
import type { PreparedQuestion, PrepareSSEEvent, TraceNodeData, InterviewTraceNodeEvent } from "@/lib/prepare-types";

function buildOpeningMessage(
  context: { target_role?: string; user_background?: string } | null,
): string {
  if (context?.target_role) {
    const bg = context.user_background
      ? `背景：${context.user_background.slice(0, 40)}...`
      : "";
    
    return `好，今天练「**${context.target_role}**」。${bg}\n\n` +
           `本场面试包含 **5 道核心技术题**，我会针对每个回答进行 **1-2 轮深度追问**。全部结束后，系统会为你生成一份 **结构化的评估报告**。\n\n` +
           `准备好了吗？发消息「开始」我们立即进入第一题。`;
  }
  return "你好！在开始之前，请告诉我你想练习的面试岗位、公司，或特定的技术主题。\n\n" +
         "**你可以这样发起：**\n\n" +
         "**前端开发**（例如：React 性能优化、大厂面试）\n\n" +
         "**后端开发**（例如：Java/Go 微服务、高并发架构）\n\n" +
         "**移动端开发**（例如：iOS/Android 实战、跨端架构）\n\n" +
         "**Python AI Agent**（例如：RAG 优化、Agent 编排）\n\n" +
         "请直接输入你的目标（例如：「我想面字节的前端岗位」），我们将立即开始。";
}

const INITIAL_PROGRESS: InterviewProgressState = {
  stage: "opening",
  question_count: 0,
  total_questions: 5,
};

const DEV_AUTH_BYPASS_TOKEN = "dev-auth-bypass-token";
const isDevAuthBypassEnabled = process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "1";

function createPrepareTracePayload(
  status: InterviewPrepareTracePayload["status"] = "running",
): InterviewPrepareTracePayload {
  return {
    status,
    nodes: [],
    questions: [],
    summary: "",
    direction: undefined,
  };
}

/** 面试房间的单面试官流式聊天主体。 */
export function InterviewChat() {
  const { isLoaded, isSignedIn, getToken } = useAuth();

  // 1. 在组件顶层读取一次上下文，供初始消息和首次 reset 使用
  const initialContextRef = useRef<{ target_role?: string; user_background?: string; jd_text?: string; jd_url?: string } | null>(null);
  const [messages, setMessages] = useState<InterviewChatMessage[]>(() => {
    if (typeof window === "undefined") return [{ role: "assistant", content: buildOpeningMessage(null) }];
    
    const raw = sessionStorage.getItem("interview_context");
    if (raw) {
      try {
        const ctx = JSON.parse(raw);
        initialContextRef.current = ctx;
        if (ctx.target_role || ctx.jd_text || ctx.jd_url) {
          // 如果需要走预备准备流水线，首屏消息先置空
          return [];
        }
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
  const [showReportDelayed, setShowReportDelayed] = useState(false);
  const [copied, setCopied] = useState(false);

  // 阶段 3 准备流状态
  const [prepStatus, setPrepStatus] = useState<"running" | "done" | "waiting_direction" | null>(null);
  const [traceNodes, setTraceNodes] = useState<TraceNodeData[]>([]);
  const [preparedQuestions, setPreparedQuestions] = useState<PreparedQuestion[]>([]);
  const [prepSummary, setPrepSummary] = useState("");
  const [prepDirection, setPrepDirection] = useState("");

  // 当报告数据到达且流式结束时，延迟显示报告卡片，增加节奏感
  useEffect(() => {
    if (report && !isStreaming) {
      const timer = setTimeout(() => {
        setShowReportDelayed(true);
      }, 800);
      return () => clearTimeout(timer);
    } else {
      setShowReportDelayed(false);
    }
  }, [report, isStreaming]);
  const abortRef = useRef<AbortController | null>(null);
  const prepAbortRef = useRef<AbortController | null>(null);
  const assistantIndexRef = useRef<number | null>(null);
  const deltaBufferRef = useRef("");
  const frameRef = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const hasResetRef = useRef(false);
  // 防止 reset 完成前用户提前发消息重用旧 session
  const isResettingRef = useRef(false);

  // 页面加载时 abandon 旧 session，确保每次进入都是全新一轮，并按需启动准备流
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

          // 如果缓存的上下文有 target_role 或者 JD 文本，就触发多 Agent 准备流水线
          if (initialContextRef.current?.target_role || initialContextRef.current?.jd_text || initialContextRef.current?.jd_url) {
            setPrepStatus("running");
            setMessages((prev) => {
              if (prev.some(isPrepareTraceMessage)) return prev;
              return [{ role: "trace", kind: "prepare", payload: createPrepareTracePayload() }, ...prev];
            });
            runPrepare(initialContextRef.current);
          }
        }
      })
      .finally(() => {
        isResettingRef.current = false;
        sessionStorage.removeItem("interview_context");
      });
  }, [isLoaded, isSignedIn, getToken]);

  async function runPrepare(ctx: { target_role?: string; user_background?: string; jd_text?: string; jd_url?: string }) {
    prepAbortRef.current?.abort();
    const abortController = new AbortController();
    prepAbortRef.current = abortController;

    try {
      const token = isDevAuthBypassEnabled ? DEV_AUTH_BYPASS_TOKEN : (await getToken() ?? "");
      for await (const ev of startPrepareStreamFetch({
        token,
        userDirection: ctx.target_role,
        userBackground: ctx.user_background,
        jdText: ctx.jd_text,
        jdUrl: ctx.jd_url,
        signal: abortController.signal,
      })) {
        if (abortController.signal.aborted) break;
        handlePrepareEvent(ev);
      }
    } catch (err) {
      if (abortController.signal.aborted) return;
      console.error("Preparation stream failed:", err);
      fallbackFromPrepareFailure(ctx);
    }
  }

  function handlePrepareEvent(ev: PrepareSSEEvent) {
    const { event, data } = ev;

    if (event === "error") {
      fallbackFromPrepareFailure(initialContextRef.current);
      return;
    }

    if (event === "node_start") {
      const updateNodes = (prev: TraceNodeData[]) => {
        if (prev.some((n) => n.id === data.node)) {
          return prev.map((n) => n.id === data.node ? { ...n, status: "running" as const } : n);
        }
        return [
          ...prev,
          { id: data.node!, label: data.label!, title: "", status: "running" as const, tokens: "" },
        ];
      };
      setTraceNodes(updateNodes);
      updatePrepareTraceMessage((payload) => ({ ...payload, nodes: updateNodes(payload.nodes) }));
    }

    if (event === "node_token") {
      const updateNodes = (prev: TraceNodeData[]) =>
        prev.map((n) =>
          n.id === data.node ? { ...n, tokens: n.tokens + (data.text ?? "") } : n
        );
      setTraceNodes(updateNodes);
      updatePrepareTraceMessage((payload) => ({ ...payload, nodes: updateNodes(payload.nodes) }));
    }

    if (event === "node_done") {
      const updateNodes = (prev: TraceNodeData[]) =>
        prev.map((n) =>
          n.id === data.node
            ? { ...n, status: "done" as const, elapsedMs: data.elapsed_ms }
            : n
        );
      setTraceNodes(updateNodes);
      updatePrepareTraceMessage((payload) => ({ ...payload, nodes: updateNodes(payload.nodes) }));
      // need_direction 由 master node_done 携带，在这里处理
      if (data.node === "master" && data.need_direction && prepStatus !== "waiting_direction") {
        setPrepStatus("waiting_direction");
        updatePrepareTraceMessage((payload) => ({ ...payload, status: "waiting_direction" }));
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "你好！我为你检测了历史表现，发现你目前还没有设置本次练习的明确岗位。请告诉我你想练习什么岗位或面试方向？（如「AI Agent 工程师」）",
          },
        ]);
      }
    }

    if (event === "done") {
      setPreparedQuestions(data.prepared_questions ?? []);
      setPrepSummary(data.summary ?? "");
      setPrepDirection(data.direction ?? "");
      setPrepStatus("done");
      updatePrepareTraceMessage((payload) => ({
        ...payload,
        status: "done",
        questions: data.prepared_questions ?? [],
        summary: data.summary ?? "",
        direction: data.direction,
      }));
    }
  }

  function updatePrepareTraceMessage(
    updater: (payload: InterviewPrepareTracePayload) => InterviewPrepareTracePayload,
  ) {
    setMessages((prev) =>
      prev.map((message) =>
        isPrepareTraceMessage(message)
          ? { ...message, payload: updater(message.payload) }
          : message,
      ),
    );
  }

  function fallbackFromPrepareFailure(
    ctx: { target_role?: string; user_background?: string } | null,
  ) {
    setPrepStatus(null);
    setTraceNodes([]);
    setPreparedQuestions([]);
    setPrepSummary("");
    setPrepDirection("");
    setMessages((prev) => {
      const withoutPrepare = prev.filter((message) => !isPrepareTraceMessage(message));
      return withoutPrepare.length > 0 ? withoutPrepare : [{ role: "assistant", content: buildOpeningMessage(ctx) }];
    });
  }

  function updateTurnTrace(turnId: string, ev: InterviewTraceNodeEvent) {
    setMessages((prev) =>
      prev.map((m) => {
        if (!isTurnTraceMessage(m) || m.id !== turnId) return m;
        const nodes = [...m.payload.nodes];
        const idx = nodes.findIndex((n) => n.id === ev.node);

        if (ev.phase === "start") {
          if (idx === -1) {
            nodes.push({
              id: ev.node,
              label: ev.label ?? ev.node,
              status: "running" as const,
              tokens: "",
            });
          } else {
            nodes[idx] = { ...nodes[idx], status: "running" as const };
          }
        } else if (ev.phase === "token") {
          if (idx !== -1) {
            nodes[idx] = { ...nodes[idx], tokens: nodes[idx].tokens + (ev.text ?? "") };
          }
        } else if (ev.phase === "done") {
          if (idx !== -1) {
            nodes[idx] = {
              ...nodes[idx],
              status: "done" as const,
              elapsedMs: ev.elapsedMs,
            };
          }
        }

        const summaryScore =
          ev.phase === "done" && ev.node === "evaluator"
            ? ev.summaryScore ?? m.payload.summaryScore
            : m.payload.summaryScore;
        const chain = ev.phase === "done" && ev.node === "master" ? ev.chain : m.payload.chain;

        return {
          ...m,
          payload: { ...m.payload, nodes, summaryScore, chain },
        };
      })
    );
  }

  function finishTurnTrace(turnId: string) {
    setMessages((prev) =>
      prev.map((m) =>
        isTurnTraceMessage(m) && m.id === turnId
          ? { ...m, payload: { ...m.payload, status: "done" as const } }
          : m
      )
    );
  }

  async function handleStartFirstQuestion() {
    if (isStreaming || isResettingRef.current) return;

    abortRef.current?.abort();
    const abortController = new AbortController();
    abortRef.current = abortController;

    const turnId = crypto.randomUUID();
    const turnIndex = 1;

    const assistantIndex = messages.length + 2;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: "开始本轮面试" },
      {
        role: "trace",
        kind: "turn",
        id: turnId,
        payload: {
          status: "running",
          nodes: [],
          turnIndex,
        },
      },
      { role: "assistant", content: "" },
    ]);
    setPrepStatus(null);

    assistantIndexRef.current = assistantIndex;
    discardBufferedDelta();
    setIsStreaming(true);

    try {
      const token = await getInterviewToken({ getToken });
      if (!token) {
        throw new Error("登录状态已失效，请重新登录后再试");
      }

      await streamInterviewChat({
        token,
        message: "__START__",
        preparedQuestions,
        signal: abortController.signal,
        onState: setProgress,
        onReport: setReport,
        onDelta: (text) => {
          deltaBufferRef.current += text;
          scheduleDeltaFlush();
        },
        onTraceNode: (ev) => updateTurnTrace(turnId, ev),
      });
      flushBufferedDelta();
      finishTurnTrace(turnId);
    } catch (error) {
      if (abortController.signal.aborted) return;

      discardBufferedDelta();
      const message = error instanceof Error ? error.message : "AI 暂时无法响应，请稍后重试";
      setMessages((current) =>
        current.map((item, index) =>
          index === assistantIndex && isTextMessage(item) ? { ...item, content: message } : item
        )
      );
    } finally {
      if (!abortController.signal.aborted) {
        setIsStreaming(false);
      }
      assistantIndexRef.current = null;
    }
  }

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      prepAbortRef.current?.abort();
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
        index === assistantIndex && isTextMessage(message)
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
    setPrepStatus(null);
    setTraceNodes([]);
    setPreparedQuestions([]);
    setPrepSummary("");
    setPrepDirection("");
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
      .filter(isTextMessage)
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

    // 若当前处于等待面试练习方向的交互追问阶段
    if (prepStatus === "waiting_direction") {
      setMessages((prev) => [...prev, { role: "user", content }]);
      setPrepStatus("running");
      updatePrepareTraceMessage((payload) => ({ ...payload, status: "running" }));
      
      try {
        const token = isDevAuthBypassEnabled ? DEV_AUTH_BYPASS_TOKEN : (await getToken() ?? "");
        for await (const ev of resumePrepareStreamFetch({
          token,
          direction: content,
          userBackground: initialContextRef.current?.user_background || undefined,
        })) {
          handlePrepareEvent(ev);
        }
      } catch (err) {
        console.error("Resume prepare failed:", err);
        setPrepStatus(null);
      }
      return;
    }

    if (progress.stage === "opening" && prepStatus === null && !report) {
      setMessages((prev) => [
        ...prev,
        { role: "user", content },
        { role: "trace", kind: "prepare", payload: createPrepareTracePayload() },
      ]);
      setPrepStatus("running");
      setTraceNodes([]);
      setPreparedQuestions([]);
      setPrepSummary("");
      setPrepDirection("");
      await runPrepare({
        target_role: content,
        user_background: initialContextRef.current?.user_background,
      });
      return;
    }

    abortRef.current?.abort();
    const abortController = new AbortController();
    abortRef.current = abortController;

    const turnId = crypto.randomUUID();
    const turnIndex = (progress.question_count ?? 0) + 1;

    // 修复 Bug：如果上一轮已结束并生成了报告，再次说话时自动开启新一轮，清空旧视觉状态
    const shouldReset = !!report || progress.stage === "closing";
    
    const userMessage: InterviewChatMessage = { role: "user", content };
    const traceMessage: InterviewChatMessage = {
      role: "trace",
      kind: "turn",
      id: turnId,
      payload: {
        status: "running",
        nodes: [],
        turnIndex,
      },
    };
    const assistantMessage: InterviewChatMessage = { role: "assistant" as const, content: "" };

    const assistantIndex = shouldReset ? 2 : messages.length + 2;
    const nextMessages = shouldReset 
      ? [userMessage, traceMessage, assistantMessage]
      : [...messages, userMessage, traceMessage, assistantMessage];

    if (shouldReset) {
      setReport(null);
      setProgress(INITIAL_PROGRESS);
    }

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
        onTraceNode: (ev) => updateTurnTrace(turnId, ev),
      });
      flushBufferedDelta();
      finishTurnTrace(turnId);
    } catch (error) {
      if (abortController.signal.aborted) return;

      discardBufferedDelta();
      const message = error instanceof Error ? error.message : "AI 暂时无法响应，请稍后重试";
      setMessages((current) =>
        current.map((item, index) =>
          index === assistantIndex && isTextMessage(item) ? { ...item, content: message } : item,
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
    <section className="relative mx-auto flex h-[calc(100dvh-132px)] min-h-0 w-full max-w-[960px] overflow-hidden rounded-2xl border border-black/10 bg-white shadow-lg shadow-black/5 dark:border-white/10 dark:bg-[#1c1c1a]">
      <div
        className="pointer-events-none absolute right-[5%] top-[18%] z-0 h-[350px] w-[350px] rounded-full bg-[radial-gradient(circle,rgba(83,74,183,0.08)_0%,rgba(244,63,94,0.04)_50%,transparent_100%)] blur-3xl"
        aria-hidden="true"
      />

      <div className="relative z-10 flex min-h-0 w-full flex-col">
        <header className="flex min-h-14 shrink-0 flex-wrap items-center justify-between gap-3 border-b border-black/10 px-5 py-3 dark:border-white/10">
          <div>
            <h1 className="bg-gradient-to-br from-[#534AB7] to-rose-600 bg-clip-text text-sm font-bold tracking-[-0.02em] text-transparent">
              AI 模拟面试舱 · Agent Cabin
            </h1>
            <p className="mt-1 text-xs text-black/45 dark:text-white/45">
              {formatStageLabel(progress.stage)}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="icon-sm"
              onClick={handleCopyChat}
              disabled={messages.length === 0}
              className="border-black/10 hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/5 disabled:pointer-events-none disabled:opacity-50"
              title="复制当前全部会话内容"
              aria-label={copied ? "已复制" : "复制会话"}
            >
              {copied ? (
                <Check className="size-3.5 text-green-600 dark:text-green-500" />
              ) : (
                <Copy className="size-3.5 text-black/60 dark:text-white/60" />
              )}
            </Button>
            <InterviewProgress progress={progress} />
          </div>
        </header>

        <div className="interview-chat-scroll flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-5 py-5">
          {messages.map((message, index) => {
            if (isPrepareTraceMessage(message)) {
              return (
                <PreparationCard
                  key={`prepare-${index}`}
                  status={message.payload.status}
                  nodes={message.payload.nodes}
                  questions={message.payload.questions}
                  summary={message.payload.summary}
                  direction={message.payload.direction}
                  onStart={handleStartFirstQuestion}
                />
              );
            }
            if (isTurnTraceMessage(message)) {
              return (
                <TurnTraceCard
                  key={`turn-${message.id}`}
                  status={message.payload.status}
                  nodes={message.payload.nodes}
                  turnIndex={message.payload.turnIndex}
                  summaryScore={message.payload.summaryScore}
                />
              );
            }
            return (
              <MessageBubble
                key={`${message.role}-${index}`}
                message={message}
                isPending={isStreaming && index === messages.length - 1}
              />
            );
          })}
          {showReportDelayed && report && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-1000">
              <div className="flex items-center gap-3 py-4" role="separator" aria-label="面试结束">
                <div className="flex-1 border-t border-black/10 dark:border-white/10" />
                <span className="shrink-0 text-xs font-medium text-black/35 dark:text-white/35">面试结束 · 评估报告已生成</span>
                <div className="flex-1 border-t border-black/10 dark:border-white/10" />
              </div>
              <ReportCard report={report} />
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {progress.stage === "closing" && showReportDelayed && (
          <div className="shrink-0 px-5 pb-8 animate-in fade-in duration-700 delay-300">
            <Button 
              onClick={handleNewRound}
              className="h-11 w-full bg-[#534AB7] text-sm font-bold text-white shadow-lg shadow-[#534AB7]/20 hover:bg-[#534AB7]/90 active:scale-[0.98] dark:bg-[#534AB7] dark:hover:bg-[#534AB7]/90"
            >
              开启下一场模拟面试
            </Button>
            <p className="mt-2 text-center text-[10px] text-black/30 dark:text-white/30">
              点击上方按钮，重新设置目标岗位与背景
            </p>
          </div>
        )}
        <ChatInput
          onSend={handleSend}
          isStreaming={isStreaming || (prepStatus !== null && prepStatus !== "waiting_direction")}
        />
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
  if (progress.stage === "opening") return null;

  const total = Math.max(progress.total_questions, 1);
  const current = Math.min(Math.max(progress.question_count, 0), total);
  const percent = progress.stage === "closing" ? 100 : Math.round((current / total) * 100);

  return (
    <div className="flex min-w-[168px] flex-col gap-1.5" aria-label="面试进度">
      <div className="flex items-center justify-between text-xs font-medium text-black/60 dark:text-white/60">
        <span>{`第 ${current}/${total} 题`}</span>
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
  if (stage === "opening") return "待命 · 准备开始";
  if (stage === "closing") return "本轮面试已结束";
  return "正式面试进行中";
}
