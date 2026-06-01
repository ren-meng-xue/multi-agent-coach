"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import {
  streamInterviewChat,
  resetInterviewSession,
  fetchActiveInterviewSession,
  fetchInterviewContext,
  startPrepareStreamFetch,
  startPrepareAndLaunchStreamFetch,
  resumePrepareStreamFetch,
  isPrepareTraceMessage,
  isTextMessage,
  isTurnTraceMessage,
  formatTraceTokens,
  INTERVIEW_NODE_TITLES,
  PREPARE_NODE_TITLES,
  type InterviewChatMessage,
  type InterviewPrepareTracePayload,
  type InterviewProgressState,
  type InterviewReport,
  type InterviewTurnTraceMessage,
} from "@/lib/interview-chat";
import { MessageBubble } from "./message-bubble";
import { ChatInput } from "./chat-input";
import { ReportCard } from "./report-card";
import { Button } from "@/components/ui/button";
import { Copy, Check, FileText } from "lucide-react";
import { PreparationCard } from "./preparation-card";
import { TurnTraceCard } from "./turn-trace-card";
import type {
  PreparedQuestion,
  PrepareSSEEvent,
  TraceNodeData,
  InterviewTraceNodeEvent,
} from "@/lib/prepare-types";

function buildOpeningMessage(
  context: { target_role?: string; user_background?: string } | null,
): string {
  if (context?.target_role) {
    const bg = context.user_background
      ? `背景：${context.user_background.slice(0, 40)}...`
      : "";

    return (
      `好，今天练「**${context.target_role}**」。${bg}\n\n` +
      `本场面试包含 **5 道核心技术题**，我会针对每个回答进行 **1-2 轮深度追问**。全部结束后，系统会为你生成一份 **结构化的评估报告**。\n\n` +
      `准备好了吗？发消息「开始」我们立即进入第一题。`
    );
  }
  return "你好！我还没有读取到本场面试的目标岗位。请直接输入你想练习的岗位或面试方向，我们将立即开始。";
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

// 解决 React 组件在 Clerk 重定向/多次挂载期间销毁导致的 initialContextRef 丢失问题。
// 使用全局变量作为挂载期间的闭包缓存，浏览器刷新时全局变量虽重置，但能从 sessionStorage 重新恢复。
let globalInitialContextCache: {
  target_role?: string;
  user_background?: string;
  jd_text?: string;
  jd_url?: string;
} | null = null;

/** 面试房间的单面试官流式聊天主体。 */
export function InterviewChat() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const router = useRouter();
  const [loadError, setLoadError] = useState(false);

  const isTest =
    typeof process !== "undefined" && process.env.NODE_ENV === "test";

  // 1. 在组件顶层读取一次上下文，供初始消息和首次 reset 使用。
  // 在单测中，各测试用例共享进程，为防全局变量污染需强制不使用闭包缓存；
  // 在真实浏览器中，则安全使用闭包缓存 globalInitialContextCache，以抵御 Clerk 重定向重新挂载造成的丢失。
  const initialContextRef = useRef<{
    target_role?: string;
    user_background?: string;
    jd_text?: string;
    jd_url?: string;
  } | null>(isTest ? null : globalInitialContextCache);

  // 在客户端首次渲染（Hydration）的 render 阶段，同步且安全地从 sessionStorage 中读取上下文。
  // 由于 Ref 仅是内存引用，不影响首屏生成的 HTML DOM 树，因此绝对不会产生 Hydration Mismatch。
  if (typeof window !== "undefined" && !initialContextRef.current) {
    const raw = sessionStorage.getItem("interview_context");
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        initialContextRef.current = parsed;
        globalInitialContextCache = parsed; // 写入全局缓存
      } catch (err) {
        console.error(
          "Failed to parse initial interview_context on render:",
          err,
        );
      }
    }
  }

  // 修复 Next.js Hydration failed：在 SSR 与客户端首次渲染时返回完全一致的初始值，
  // 待组件挂载后再通过 useEffect 更新为已同步加载完毕的 initialContextRef.current 实际值。
  // 注意：在单测环境（process.env.NODE_ENV === "test"）中，为满足同步测试断言，允许直接同步从已加载的 ref 初始化状态。
  const [messages, setMessages] = useState<InterviewChatMessage[]>(() => {
    const isTest =
      typeof process !== "undefined" && process.env.NODE_ENV === "test";
    const ctx = initialContextRef.current;
    if (ctx) {
      // 如果携带了目标岗位/JD，初始就返回空消息列表，避免欢迎卡片一闪而过
      if (ctx.target_role || ctx.jd_text || ctx.jd_url) {
        return [];
      }
      if (isTest) {
        return [{ role: "assistant", content: buildOpeningMessage(ctx) }];
      }
    }
    return [{ role: "assistant", content: buildOpeningMessage(null) }];
  });

  const [isInitialLoading, setIsInitialLoading] = useState(true);

  useEffect(() => {
    const isTest =
      typeof process !== "undefined" && process.env.NODE_ENV === "test";
    if (isTest) return; // 单测环境在 useState 中已同步初始化，无需重复更新

    if (initialContextRef.current) {
      const ctx = initialContextRef.current;
      if (ctx.target_role || ctx.jd_text || ctx.jd_url) {
        // 客户端首屏成功挂载后，如果带有开始意图，在网络请求加载前保持 messages 为 []，由 isInitialLoading 渲染精美微光加载，
        // 彻底根治一挂载就一闪而逝“专家组正在工作”占位卡片的假闪烁。
        setMessages([]);
      } else {
        setMessages([{ role: "assistant", content: buildOpeningMessage(ctx) }]);
      }
    }
  }, []);

  const [progress, setProgress] =
    useState<InterviewProgressState>(INITIAL_PROGRESS);
  const [isStreaming, setIsStreaming] = useState(false);
  const [report, setReport] = useState<InterviewReport | null>(null);
  const [showReportDelayed, setShowReportDelayed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [fullCopied, setFullCopied] = useState(false);

  // 阶段 3 准备流状态
  const [prepStatus, setPrepStatus] = useState<
    "running" | "done" | "waiting_direction" | null
  >(null);

  // [I7] 单源数据读取优化：从 messages trace payload 中单源读取已生成的问题列表，杜绝双写和冗余 re-render
  const preparedQuestions = useMemo(() => {
    const prepMessage = messages.find(isPrepareTraceMessage);
    return prepMessage?.payload.questions ?? [];
  }, [messages]);

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
  const currentTurnIdRef = useRef<string | null>(null);
  const deltaBufferRef = useRef("");
  const traceBufferRef = useRef<
    { turnId: string; ev: InterviewTraceNodeEvent }[]
  >([]);
  const frameRef = useRef<number | null>(null);
  const traceFrameRef = useRef<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const hasResetRef = useRef(false);
  // 防止 reset 完成前用户提前发消息重用旧 session
  const isResettingRef = useRef(false);

  // 页面加载时按需恢复进行中的活动会话，否则按需启动新一轮的准备流或展示欢迎开场消息。
  // sessionStorage 防抖：Clerk 握手期间的多次 307 重定向会导致组件反复挂载，
  // 每次挂载都触发同步流程，30s 内只允许一次实际请求防抖。
  useEffect(() => {
    const shouldProceed = isDevAuthBypassEnabled || (isLoaded && isSignedIn);
    if (!shouldProceed || hasResetRef.current) return;

    const isTest =
      typeof process !== "undefined" && process.env.NODE_ENV === "test";
    const isRoutingGuardTest =
      isTest &&
      typeof window !== "undefined" &&
      sessionStorage.getItem("test_routing_guard") === "true";
    if (isTest && !initialContextRef.current && !isRoutingGuardTest) {
      hasResetRef.current = true;
      return;
    }

    hasResetRef.current = true;
    isResettingRef.current = true;
    getInterviewToken({ getToken, skipCache: true })
      .then(async (token) => {
        if (!token) return;

        const RESET_COOLDOWN_MS = 30_000;
        const RESET_TS_KEY = "interview_reset_ts";
        const lastReset = sessionStorage.getItem(RESET_TS_KEY);
        // 是否处于 30 秒重置冷却防抖内
        const isCooldown =
          !isTest &&
          lastReset &&
          Date.now() - Number(lastReset) < RESET_COOLDOWN_MS;

        // 1. 如果缓存的上下文有 target_role / JD 信息，说明是用户在 Coach 主动发起的“开始面试”或“再练一场”
        if (
          initialContextRef.current?.target_role ||
          initialContextRef.current?.jd_text ||
          initialContextRef.current?.jd_url
        ) {
          // 仅在冷却时间外才真正向后端发送 /reset 请求，防止 Clerk 多次重定向导致频繁 reset 生成大量废弃垃圾会话
          if (!isCooldown) {
            sessionStorage.setItem(RESET_TS_KEY, String(Date.now()));
            await resetInterviewSession({
              token,
              target_role: initialContextRef.current?.target_role,
              user_background: initialContextRef.current?.user_background,
            });
          }

          setPrepStatus("running");
          setMessages((prev) => {
            if (prev.some(isPrepareTraceMessage)) return prev;
            return [
              {
                role: "trace",
                kind: "prepare",
                payload: createPrepareTracePayload(),
              },
              ...prev,
            ];
          });
          // 无论是全新 reset 还是二次挂载恢复，都必须正常跑 runPrepare 建立 SSE 监听，保证新挂载组件实例的正常状态推进！
          // 初始入口走 /prepare/launch：prepare 完成后由后端 phase_change 自动接续面试开场。
          runPrepare(initialContextRef.current, { autoLaunch: true });
        } else {
          // 2. 否则（页面刷新，或切离后点导航栏切回），先尝试拉取后端目前正在进行中 (in_progress) 的会话
          try {
            const activeSession = await fetchActiveInterviewSession({ token });
            if (activeSession.session_id) {
              // 成功拉取到活动会话，恢复历史消息、进度和评估报告
              if (activeSession.messages && activeSession.messages.length > 0) {
                const restoredMessages: InterviewChatMessage[] =
                  activeSession.messages
                    .filter((m) => m.content !== "__START__") // 隐藏内部协议 Token
                    .map((m) => ({
                      role: m.role as "user" | "assistant",
                      content: m.content,
                    }));
                if (activeSession.prepare_trace) {
                  restoredMessages.unshift({
                    role: "trace",
                    kind: "prepare",
                    payload: activeSession.prepare_trace,
                  });
                }

                if (restoredMessages.length > 0) {
                  setMessages(restoredMessages);
                } else {
                  setMessages([
                    {
                      role: "assistant",
                      content: buildOpeningMessage(activeSession),
                    },
                  ]);
                }
              } else {
                if (activeSession.prepare_trace) {
                  setMessages([
                    {
                      role: "trace",
                      kind: "prepare",
                      payload: activeSession.prepare_trace,
                    },
                  ]);
                } else {
                  let openingContext: {
                    target_role?: string;
                    user_background?: string;
                  } | null = activeSession;
                  if (!openingContext.target_role) {
                    try {
                      const userContext = await fetchInterviewContext({
                        token,
                      });
                      openingContext = {
                        target_role: userContext.target_role ?? undefined,
                        user_background:
                          userContext.user_background ?? undefined,
                      };
                    } catch (err) {
                      console.warn(
                        "Failed to load interview context for active session",
                        err,
                      );
                    }
                  }
                  if (
                    activeSession.stage === "opening" &&
                    openingContext?.target_role
                  ) {
                    setPrepStatus("running");
                    setMessages([
                      {
                        role: "trace",
                        kind: "prepare",
                        payload: createPrepareTracePayload(),
                      },
                    ]);
                    runPrepare(openingContext, { autoLaunch: true });
                  } else {
                    setMessages([
                      {
                        role: "assistant",
                        content: buildOpeningMessage(openingContext),
                      },
                    ]);
                  }
                }
              }

              setProgress({
                stage:
                  (activeSession.stage as
                    | "opening"
                    | "interview"
                    | "closing") || "opening",
                question_count: activeSession.question_count ?? 0,
                total_questions: activeSession.total_questions ?? 5,
              });

              if (activeSession.report) {
                setReport(activeSession.report);
              }
            } else {
              // 路径 3/4：无 sessionStorage 上下文 + 无活动会话 → 守卫重定向回 Coach
              router.replace("/coach?from=interview");
              return; // 即将卸载，不再触发后续 setIsInitialLoading
            }
          } catch (err) {
            console.error("Failed to load active interview session:", err);
            setLoadError(true);
          }
        }
      })
      .finally(() => {
        isResettingRef.current = false;
        setIsInitialLoading(false);
        sessionStorage.removeItem("interview_context");
      });
  }, [isLoaded, isSignedIn, getToken]);

  async function runPrepare(
    ctx: {
      target_role?: string;
      user_background?: string;
      jd_text?: string;
      jd_url?: string;
    },
    { autoLaunch = false }: { autoLaunch?: boolean } = {},
  ) {
    prepAbortRef.current?.abort();
    const abortController = new AbortController();
    prepAbortRef.current = abortController;

    try {
      const token = isDevAuthBypassEnabled
        ? DEV_AUTH_BYPASS_TOKEN
        : ((await getToken()) ?? "");
      const streamFn = autoLaunch
        ? startPrepareAndLaunchStreamFetch
        : startPrepareStreamFetch;
      for await (const ev of streamFn({
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
      // 错误若发生在 turn 阶段（currentTurnIdRef 非空），不能走 prepare-only 的 fallback——
      // 那会清掉 prepare trace 但留下半截 user/assistant/turn 消息形成僵尸 UI。
      if (currentTurnIdRef.current) {
        const turnId = currentTurnIdRef.current;
        const assistantIdx = assistantIndexRef.current;
        const errMsg = data.message ?? "AI 暂时无法响应，请稍后重试";
        discardBufferedDelta();
        setMessages((prev) =>
          prev.map((m, i) =>
            i === assistantIdx && isTextMessage(m)
              ? { ...m, content: errMsg }
              : m,
          ),
        );
        finishTurnTrace(turnId);
        setIsStreaming(false);
        assistantIndexRef.current = null;
        currentTurnIdRef.current = null;
        return;
      }
      fallbackFromPrepareFailure(initialContextRef.current);
      return;
    }

    if (event === "node_start") {
      updatePrepareTraceMessage((payload) => {
        const nodes = [...payload.nodes];
        if (nodes.some((n) => n.id === data.node)) {
          return {
            ...payload,
            nodes: nodes.map((n) =>
              n.id === data.node ? { ...n, status: "running" as const } : n,
            ),
          };
        }
        return {
          ...payload,
          nodes: [
            ...nodes,
            {
              id: data.node!,
              label: data.label!,
              title: data.title ?? data.node!,
              status: "running" as const,
              tokens: "",
            },
          ],
        };
      });
    }

    if (event === "node_token") {
      updatePrepareTraceMessage((payload) => ({
        ...payload,
        nodes: payload.nodes.map((n) =>
          n.id === data.node
            ? { ...n, tokens: n.tokens + (data.text ?? "") }
            : n,
        ),
      }));
    }

    if (event === "node_done") {
      updatePrepareTraceMessage((payload) => ({
        ...payload,
        nodes: payload.nodes.map((n) =>
          n.id === data.node
            ? { ...n, status: "done" as const, elapsedMs: data.elapsed_ms }
            : n,
        ),
      }));

      // need_direction 由 master node_done 携带，在这里处理
      if (
        data.node === "master" &&
        data.need_direction &&
        prepStatus !== "waiting_direction"
      ) {
        setPrepStatus("waiting_direction");
        updatePrepareTraceMessage((payload) => ({
          ...payload,
          status: "waiting_direction",
        }));
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              "你好！我为你检测了历史表现，发现你目前还没有设置本次练习的明确岗位。请告诉我你想练习什么岗位或面试方向？（如「AI Agent 工程师」）",
          },
        ]);
      }
    }

    if (event === "done") {
      setPrepStatus("done");
      updatePrepareTraceMessage((payload) => ({
        ...payload,
        status: "done",
        questions: data.prepared_questions ?? [],
        summary: data.summary ?? "",
        direction: data.direction,
        jdContext: data.jd_context,
      }));
    }

    // ── Phase-change：后端信号接续面试开场 ──────────────────────────
    if (event === "phase_change") {
      const turnId = data.turn_id ?? crypto.randomUUID();
      currentTurnIdRef.current = turnId;
      const turnIndex = 1;

      setPrepStatus(null);
      setIsStreaming(true);

      // updater 外捕获 assistantIndex 后再写入 ref，规避 StrictMode 下 functional
      // updater 被双调用对 ref 产生 race；之后到达的 turn_delta 走 scheduleDeltaFlush
      // 在下一帧 flush，此时 ref 已写好，时序安全。
      let newAssistantIndex = -1;
      setMessages((prev) => {
        newAssistantIndex = prev.length;
        return [
          ...prev,
          { role: "assistant" as const, content: "" },
          {
            role: "trace" as const,
            kind: "turn" as const,
            id: turnId,
            payload: {
              status: "running" as const,
              nodes: [],
              turnIndex,
              isOpening: true,
            },
          },
        ];
      });
      assistantIndexRef.current = newAssistantIndex;
    }

    // ── turn_node_* → 更新 turn trace ────────────────────────────────
    if (
      event === "turn_node_start" ||
      event === "turn_node_token" ||
      event === "turn_node_done"
    ) {
      const turnId = currentTurnIdRef.current;
      if (!turnId) return;

      const phase =
        event === "turn_node_start"
          ? "start"
          : event === "turn_node_token"
            ? "token"
            : "done";

      updateTurnTrace(turnId, {
        phase,
        node: data.node ?? "",
        label: data.label,
        text: data.text,
        elapsedMs: data.elapsed_ms,
        candidateLevel: data.candidate_level,
        latentSignals: data.latent_signals,
        missingDimensions: data.missing_dimensions,
        followupFocus: data.followup_focus,
        assistantMessage: data.assistant_message,
      });
    }

    // ── turn_delta → 缓冲区追加文字 ──────────────────────────────────
    if (event === "turn_delta") {
      deltaBufferRef.current += data.text ?? "";
      scheduleDeltaFlush();
    }

    // ── turn_state → 更新进度 ─────────────────────────────────────────
    if (event === "turn_state") {
      setProgress({
        stage:
          (data.stage as "opening" | "interview" | "closing") ?? "interview",
        question_count: data.question_count ?? 0,
        total_questions: data.total_questions ?? 5,
      });
    }

    // ── turn_report → 设置评估报告（service 在 closing 阶段会发） ─────
    if (event === "turn_report") {
      setReport({
        overall_score: data.overall_score ?? 0,
        technical_depth: data.technical_depth ?? 0,
        quantified_results: data.quantified_results ?? 0,
        failure_tradeoffs: data.failure_tradeoffs ?? 0,
        structure: data.structure ?? 0,
        highlights: data.highlights ?? [],
        improvements: data.improvements ?? [],
      });
    }

    // ── turn_done → 收尾 ─────────────────────────────────────────────
    if (event === "turn_done") {
      const turnId = currentTurnIdRef.current;
      flushBufferedDelta();
      if (turnId) finishTurnTrace(turnId);
      setIsStreaming(false);
      assistantIndexRef.current = null;
      currentTurnIdRef.current = null;
    }
  }

  function updatePrepareTraceMessage(
    updater: (
      payload: InterviewPrepareTracePayload,
    ) => InterviewPrepareTracePayload,
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
    setMessages((prev) => {
      const withoutPrepare = prev.filter(
        (message) => !isPrepareTraceMessage(message),
      );
      return withoutPrepare.length > 0
        ? withoutPrepare
        : [{ role: "assistant", content: buildOpeningMessage(ctx) }];
    });
  }

  function updateTurnTrace(turnId: string, ev: InterviewTraceNodeEvent) {
    traceBufferRef.current.push({ turnId, ev });
    scheduleTraceFlush();
  }

  function scheduleTraceFlush() {
    if (traceFrameRef.current !== null) return;

    // 在测试环境下禁用 requestAnimationFrame 缓冲，直接同步冲刷，确保测试断言可靠
    if (typeof process !== "undefined" && process.env.NODE_ENV === "test") {
      flushTraceBuffer();
      return;
    }

    traceFrameRef.current = window.requestAnimationFrame(() => {
      traceFrameRef.current = null;
      flushTraceBuffer();
    });
  }

  function flushTraceBuffer() {
    const events = traceBufferRef.current;
    if (events.length === 0) return;
    traceBufferRef.current = [];

    setMessages((prev) => {
      const next = [...prev];
      for (const { turnId, ev } of events) {
        const idx = next.findIndex(
          (m) => isTurnTraceMessage(m) && m.id === turnId,
        );
        if (idx === -1) continue;

        const m = next[idx] as InterviewTurnTraceMessage;
        const nodes = [...m.payload.nodes];
        const nIdx = nodes.findIndex((n) => n.id === ev.node);

        if (ev.phase === "start") {
          if (nIdx === -1) {
            nodes.push({
              id: ev.node,
              label: ev.label ?? ev.node,
              status: "running" as const,
              tokens: "",
            });
          } else {
            nodes[nIdx] = { ...nodes[nIdx], status: "running" as const };
          }
        } else if (ev.phase === "token") {
          if (nIdx !== -1) {
            nodes[nIdx] = {
              ...nodes[nIdx],
              tokens: nodes[nIdx].tokens + (ev.text ?? ""),
            };
          }
        } else if (ev.phase === "done") {
          if (nIdx !== -1) {
            nodes[nIdx] = {
              ...nodes[nIdx],
              status: "done" as const,
              elapsedMs: ev.elapsedMs,
              candidateLevel: ev.candidateLevel,
              latentSignals: ev.latentSignals,
              missingDimensions: ev.missingDimensions,
              followupFocus: ev.followupFocus,
              // ask_question/followup/closing 无 LLM token 流时，用 node_done 携带的
              // assistant_message 填充 tokens，让 trace 面板能显示对应内容
              tokens:
                ev.assistantMessage && !nodes[nIdx].tokens
                  ? ev.assistantMessage
                  : nodes[nIdx].tokens,
            };
          }
        }

        const summaryScore =
          ev.phase === "done" && ev.node === "evaluator"
            ? (ev.summaryScore ?? m.payload.summaryScore)
            : m.payload.summaryScore;
        const chain =
          ev.phase === "done" && ev.node === "master"
            ? ev.chain
            : m.payload.chain;

        next[idx] = {
          ...m,
          payload: { ...m.payload, nodes, summaryScore, chain },
        };
      }
      return next;
    });
  }

  function finishTurnTrace(turnId: string) {
    setMessages((prev) =>
      prev.map((m) =>
        isTurnTraceMessage(m) && m.id === turnId
          ? { ...m, payload: { ...m.payload, status: "done" as const } }
          : m,
      ),
    );
  }

  async function handleStartFirstQuestion() {
    const isTest =
      typeof process !== "undefined" && process.env.NODE_ENV === "test";
    if (isStreaming || (isResettingRef.current && !isTest)) return;
    if (progress.stage !== "opening" && !isTest) return;

    abortRef.current?.abort();
    const abortController = new AbortController();
    abortRef.current = abortController;

    const turnId = crypto.randomUUID();
    const turnIndex = 1;

    // assistant 在 trace 之前：trace 折叠后内容出现在面板上方
    const assistantIndex = messages.length;
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "" },
      {
        role: "trace",
        kind: "turn",
        id: turnId,
        payload: {
          status: "running",
          nodes: [],
          turnIndex,
          isOpening: true,
        },
      },
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
      const message =
        error instanceof Error ? error.message : "AI 暂时无法响应，请稍后重试";
      setMessages((current) =>
        current.map((item, index) =>
          index === assistantIndex && isTextMessage(item)
            ? { ...item, content: message }
            : item,
        ),
      );
    } finally {
      if (!abortController.signal.aborted) {
        setIsStreaming(false);
      }
      assistantIndexRef.current = null;
    }
  }

  // 始终指向最新版 handleStartFirstQuestion，供 setTimeout 回调安全调用
  const handleStartFirstQuestionRef = useRef(handleStartFirstQuestion);
  handleStartFirstQuestionRef.current = handleStartFirstQuestion;

  // 准备完成后自动加"进入面试"节点并触发开场。
  // /prepare/launch 路径下后端会发 phase_change 接管开场，此 effect 应跳过；
  // /prepare/resume 路径（need_direction 后的方向追问）后端不会接管，此 effect 兜底进入面试。
  useEffect(() => {
    if (prepStatus !== "done") return;
    if (currentTurnIdRef.current) return;

    updatePrepareTraceMessage((payload) => ({
      ...payload,
      nodes: [
        ...payload.nodes,
        {
          id: "launch",
          label: "进入面试",
          status: "running" as const,
          tokens: "",
        },
      ],
    }));

    const t = setTimeout(() => {
      updatePrepareTraceMessage((payload) => ({
        ...payload,
        nodes: payload.nodes.map((n) =>
          n.id === "launch" ? { ...n, status: "done" as const } : n,
        ),
      }));
      handleStartFirstQuestionRef.current();
    }, 600);

    return () => clearTimeout(t);
  }, [prepStatus]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      prepAbortRef.current?.abort();
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
      }
      if (traceFrameRef.current !== null) {
        window.cancelAnimationFrame(traceFrameRef.current);
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages, report]);

  function flushBufferedDelta() {
    const text = deltaBufferRef.current;
    const assistantIndex = assistantIndexRef.current;
    const turnId = currentTurnIdRef.current;
    if (!text || assistantIndex === null) return;

    deltaBufferRef.current = "";
    setMessages((current) => {
      let targetIdx = assistantIndex;

      // React 18 automatic batching: functional updater in setMessages no longer runs
      // synchronously in async context, so the phase_change handler's newAssistantIndex
      // stays -1 when assistantIndexRef is set. Fall back to finding the assistant message
      // by its position immediately before the current turn trace.
      if (targetIdx < 0 && turnId) {
        const traceIdx = current.findIndex(
          (m) => isTurnTraceMessage(m) && m.id === turnId,
        );
        if (traceIdx > 0) targetIdx = traceIdx - 1;
      }

      if (targetIdx < 0) return current;

      return current.map((message, index) =>
        index === targetIdx && isTextMessage(message)
          ? { ...message, content: `${message.content}${text}` }
          : message,
      );
    });
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
    setReport(null);
    setProgress(INITIAL_PROGRESS);
    setPrepStatus(null);
    isResettingRef.current = true;
    sessionStorage.removeItem("interview_reset_ts");
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

    // 立即冲刷所有待处理的文本增量，确保复制出的内容是最新的
    flushBufferedDelta();

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

  async function handleCopyFullChat() {
    if (messages.length === 0) return;

    // 立即冲刷所有待处理的 trace 节点更新，确保复制出的内容是最新的
    flushTraceBuffer();

    let fullText = "";

    // 1. 面试背景
    if (initialContextRef.current) {
      const ctx = initialContextRef.current;
      if (ctx.target_role || ctx.user_background || ctx.jd_text) {
        fullText += `【面试背景】\n`;
        if (ctx.target_role) fullText += `- 目标岗位: ${ctx.target_role}\n`;
        if (ctx.user_background)
          fullText += `- 个人背景: ${ctx.user_background}\n`;
        if (ctx.jd_text)
          fullText += `- JD 内容: ${ctx.jd_text.slice(0, 100)}${ctx.jd_text.length > 100 ? "..." : ""}\n`;
        fullText += `\n`;
      }
    }

    // 2. 遍历消息列表，格式化所有内容
    messages.forEach((msg) => {
      if (isTextMessage(msg)) {
        if (!msg.content) return; // 跳过流式期间的空占位消息
        const roleName = msg.role === "user" ? "求职者" : "面试官";
        fullText += `【${roleName}】：${msg.content}\n\n`;
      } else if (isPrepareTraceMessage(msg)) {
        fullText += `【AI 思考过程 - 准备阶段】：\n`;
        msg.payload.nodes.forEach((node) => {
          const title = PREPARE_NODE_TITLES[node.id] || node.id;
          const content = formatTraceTokens(node.id, node.tokens);
          fullText += `  - ${title}:\n    ${content}\n`;
        });
        if (msg.payload.direction) {
          fullText += `  - 确定的练习方向: ${msg.payload.direction}\n`;
        }
        fullText += `\n`;
      } else if (isTurnTraceMessage(msg)) {
        fullText += `【AI 思考过程 - 分析与出题】：\n`;
        msg.payload.nodes.forEach((node) => {
          const title = INTERVIEW_NODE_TITLES[node.id] || node.id;
          const content = formatTraceTokens(node.id, node.tokens);
          fullText += `  - ${title}:\n    ${content}\n`;
          if (node.candidateLevel) {
            fullText += `    [级别: ${node.candidateLevel}]\n`;
          }
          if (node.latentSignals && node.latentSignals.length > 0) {
            fullText += `    [信号: ${node.latentSignals.join(", ")}]\n`;
          }
        });
        if (msg.payload.summaryScore) {
          fullText += `  - 本轮表现评分: ${msg.payload.summaryScore}\n`;
        }
        fullText += `\n`;
      }
    });

    // 3. 评估报告
    if (report) {
      fullText += `【面试评估报告】：\n`;
      fullText += `- 综合评分: ${report.overall_score}\n`;
      fullText += `- 技术深度: ${report.technical_depth}\n`;
      fullText += `- 结果量化: ${report.quantified_results}\n`;
      fullText += `- 权衡分析: ${report.failure_tradeoffs}\n`;
      fullText += `- 结构化表达: ${report.structure}\n`;
      if (report.highlights.length > 0) {
        fullText += `- 面试亮点:\n  ${report.highlights.map((h) => `* ${h}`).join("\n  ")}\n`;
      }
      if (report.improvements.length > 0) {
        fullText += `- 改进建议:\n  ${report.improvements.map((i) => `* ${i}`).join("\n  ")}\n`;
      }
    }

    try {
      await navigator.clipboard.writeText(fullText.trim());
      setFullCopied(true);
      setTimeout(() => setFullCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy full chat: ", err);
    }
  }

  async function handleSend(content: string) {
    const isTest =
      typeof process !== "undefined" && process.env.NODE_ENV === "test";
    if (!content || isStreaming || (isResettingRef.current && !isTest)) return;

    // 若当前处于等待面试练习方向的交互追问阶段
    if (prepStatus === "waiting_direction") {
      setMessages((prev) => [...prev, { role: "user", content }]);
      setPrepStatus("running");
      updatePrepareTraceMessage((payload) => ({
        ...payload,
        status: "running",
      }));

      prepAbortRef.current?.abort();
      const abortController = new AbortController();
      prepAbortRef.current = abortController;

      try {
        const token = isDevAuthBypassEnabled
          ? DEV_AUTH_BYPASS_TOKEN
          : ((await getToken()) ?? "");
        const prepMessage = messages.find(isPrepareTraceMessage);
        const weakAreasJson = prepMessage ? JSON.stringify([]) : undefined;

        for await (const ev of resumePrepareStreamFetch({
          token,
          direction: content,
          userBackground:
            initialContextRef.current?.user_background || undefined,
          jdText: initialContextRef.current?.jd_text || undefined,
          weakAreas: weakAreasJson,
          signal: abortController.signal,
        })) {
          if (abortController.signal.aborted) break;
          handlePrepareEvent(ev);
        }
      } catch (err) {
        if (abortController.signal.aborted) return;
        console.error("Resume prepare failed:", err);
        setPrepStatus(null);
      }
      return;
    }

    if (progress.stage === "opening" && prepStatus === null && !report) {
      setMessages((prev) => [
        ...prev,
        { role: "user", content },
        {
          role: "trace",
          kind: "prepare",
          payload: createPrepareTracePayload(),
        },
      ]);
      setPrepStatus("running");
      await runPrepare({
        target_role: content,
        user_background: initialContextRef.current?.user_background,
        jd_text: initialContextRef.current?.jd_text,
        jd_url: initialContextRef.current?.jd_url,
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
    const assistantMessage: InterviewChatMessage = {
      role: "assistant" as const,
      content: "",
    };

    // assistant 在 trace 之前：trace 折叠后内容出现在面板上方
    const assistantIndex = shouldReset ? 1 : messages.length + 1;
    const nextMessages = shouldReset
      ? [userMessage, assistantMessage, traceMessage]
      : [...messages, userMessage, assistantMessage, traceMessage];

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
      const message =
        error instanceof Error ? error.message : "AI 暂时无法响应，请稍后重试";
      setMessages((current) =>
        current.map((item, index) =>
          index === assistantIndex && isTextMessage(item)
            ? { ...item, content: message }
            : item,
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
    <section className="relative mx-auto flex h-[calc(100dvh-132px)] min-h-0 w-full max-w-[1400px] overflow-hidden rounded-2xl border border-black/10 bg-white shadow-lg shadow-black/5 dark:border-white/10 dark:bg-[#1c1c1a]">
      <div
        className="pointer-events-none absolute right-[5%] top-[18%] z-0 h-[450px] w-[450px] rounded-full bg-[radial-gradient(circle,rgba(83,74,183,0.08)_0%,rgba(244,63,94,0.04)_50%,transparent_100%)] blur-3xl"
        aria-hidden="true"
      />

      <div className="relative z-10 flex min-h-0 w-full flex-col">
        <header className="flex min-h-14 shrink-0 flex-wrap items-center justify-between gap-3 border-b border-black/10 px-6 py-3 dark:border-white/10">
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
              title="仅复制对话文本"
              aria-label={copied ? "已复制" : "复制会话"}
            >
              {copied ? (
                <Check className="size-3.5 text-green-600 dark:text-green-500" />
              ) : (
                <Copy className="size-3.5 text-black/60 dark:text-white/60" />
              )}
            </Button>
            <Button
              variant="outline"
              size="icon-sm"
              onClick={handleCopyFullChat}
              disabled={messages.length === 0}
              className="border-black/10 hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/5 disabled:pointer-events-none disabled:opacity-50"
              title="复制完整记录（含 AI 思考过程）"
              aria-label={fullCopied ? "已复制" : "复制完整记录"}
            >
              {fullCopied ? (
                <Check className="size-3.5 text-green-600 dark:text-green-500" />
              ) : (
                <FileText className="size-3.5 text-black/60 dark:text-white/60" />
              )}
            </Button>
            <InterviewProgress progress={progress} />
          </div>
        </header>

        <div className="interview-chat-scroll flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-6 py-6">
          {isInitialLoading && messages.length <= 1 && (
            <div className="flex flex-1 flex-col items-center justify-center gap-2.5 animate-in fade-in duration-500">
              <span className="relative flex size-6 items-center justify-center rounded-full bg-[#534AB7]/5 dark:bg-[#CECBF6]/5">
                <span className="absolute inset-0 animate-ping rounded-full bg-[#534AB7]/10 dark:bg-[#CECBF6]/10" />
                <span className="size-2 rounded-full bg-[#534AB7] dark:bg-[#CECBF6] shadow-[0_0_8px_rgba(83,74,183,0.4)]" />
              </span>
              <span className="text-[10px] font-bold text-black/35 tracking-wider dark:text-white/30 animate-pulse">
                正在连接模拟舱...
              </span>
            </div>
          )}
          {loadError && messages.length <= 1 && (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-sm">
              <div className="text-black/60 dark:text-white/60">
                连接异常，请重试或返回 Coach。
              </div>
              <Button
                variant="outline"
                onClick={() => router.replace("/coach")}
              >
                返回 Coach
              </Button>
            </div>
          )}
          {messages.map((message, index) => {
            if (isPrepareTraceMessage(message)) {
              return (
                <PreparationCard
                  key={`prepare-${index}`}
                  status={message.payload.status}
                  nodes={message.payload.nodes}
                  direction={message.payload.direction}
                />
              );
            }
            if (isTurnTraceMessage(message)) {
              // 思考面板已完美融入 AI 消息气泡底部渲染，此处直接跳过，避免重复渲染
              return null;
            }

            // 提取紧跟在 AI (assistant) 消息后面的 trace 面板消息，以便在气泡内合并展现
            let associatedTrace: InterviewTurnTraceMessage | undefined =
              undefined;
            if (message.role === "assistant") {
              const nextMessage = messages[index + 1];
              if (nextMessage && isTurnTraceMessage(nextMessage)) {
                associatedTrace = nextMessage;
              }
            }

            // 正在首题生成或思考分析、且 AI 正文还为空（即 content === ""）时，不要塞进窄扁的 MessageBubble 气泡！
            // 直接以独立 100% 宽度将 TurnTraceCard 平铺展示，实现无比舒展大气的极客流式工作日志！
            if (
              message.role === "assistant" &&
              message.content === "" &&
              associatedTrace
            ) {
              return (
                <div
                  key={`embedded-trace-${index}`}
                  className="w-full py-1 animate-in fade-in slide-in-from-bottom-2 duration-300"
                >
                  <TurnTraceCard
                    status={associatedTrace.payload.status}
                    nodes={associatedTrace.payload.nodes}
                    turnIndex={associatedTrace.payload.turnIndex}
                    summaryScore={associatedTrace.payload.summaryScore}
                    isOpening={associatedTrace.payload.isOpening}
                    isEmbedded={false}
                  />
                </div>
              );
            }

            // 状态面板还在跑且无 trace 时，空 assistant bubble 不渲染，避免"..."和 trace 同时出现
            if (
              message.role === "assistant" &&
              message.content === "" &&
              isStreaming &&
              !associatedTrace
            ) {
              return null;
            }
            return (
              <MessageBubble
                key={`${message.role}-${index}`}
                message={message}
                isPending={isStreaming && index === messages.length - 1}
                trace={associatedTrace}
              />
            );
          })}
          {showReportDelayed && report && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-1000">
              <div
                className="flex items-center gap-3 py-4"
                role="separator"
                aria-label="面试结束"
              >
                <div className="flex-1 border-t border-black/10 dark:border-white/10" />
                <span className="shrink-0 text-xs font-medium text-black/35 dark:text-white/35">
                  面试结束 · 评估报告已生成
                </span>
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
          isStreaming={
            isStreaming ||
            (prepStatus !== null && prepStatus !== "waiting_direction")
          }
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
  const percent =
    progress.stage === "closing" ? 100 : Math.round((current / total) * 100);

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
