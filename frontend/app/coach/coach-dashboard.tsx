"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import { useAuth } from "@clerk/nextjs";
import {
  Calendar,
  Star,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  XCircle,
  BrainCircuit,
} from "lucide-react";
import {
  fetchCoachOpeningMessage,
  fetchInterviewContext,
  fetchInterviewHistory,
  enterInterviewRoom,
  type CoachOpeningMessageResponse,
  type UserContextResponse,
  type InterviewHistoryItem,
} from "@/lib/interview-chat";

import {
  fetchUserStage,
  fetchLatestCoachPlan,
  type UserStage,
  type CoachPlanData,
} from "@/lib/coach";
import { readSseStream } from "@/lib/sse";

type MemorySession = {
  id: string | number;
  sessionIndex: number;
  date: string;
  topic: string;
  targetRole: string;
  score: number;
  passFail: "pass" | "fail" | "partial";
  trend: "up" | "down" | "flat";
  dimensions: {
    label: string;
    score: number;
  }[];
  highlights: string[];
  improvements: string[];
  keyConcepts: string[];
  commonMistakes: string[];
};

/** 将后端历史记录项映射为前端展示用的 MemorySession。 */
function mapHistoryItemToSession(
  item: InterviewHistoryItem,
  index: number,
  total: number,
): MemorySession {
  const report = item.report || {};
  const dimensions = [
    { label: "技术深度", score: report.technical_depth || 0 },
    { label: "量化结果", score: report.quantified_results || 0 },
    { label: "失败降级", score: report.failure_tradeoffs || 0 },
    { label: "结构表达", score: report.structure || 0 },
  ];
  const displayScore = item.score || report.overall_score || 0;
  return {
    id: item.id,
    sessionIndex: total - index,
    date: item.date,
    topic: item.topic,
    targetRole: item.target_role,
    score: displayScore,
    passFail: item.pass_fail as "pass" | "fail" | "partial",
    trend: "flat",
    dimensions,
    highlights: report.highlights || [],
    improvements: report.improvements || item.key_issues || [],
    keyConcepts: report.key_concepts || [],
    commonMistakes: report.common_mistakes || [],
  };
}

const DEV_AUTH_BYPASS_TOKEN = "dev-auth-bypass-token";
const isDevAuthBypassEnabled = process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "1";
const EMPHASIS_CLASS =
  "text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans";
const WARNING_EMPHASIS_CLASS =
  "text-[#e11d48] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(225,29,72,0.16)_62%)] font-sans";
const COACH_WARNING_TERMS = [
  "缺少具体例证",
  "缺乏具体实例",
  "不够具体",
  "缺少量化",
  "缺乏量化",
  "说服力",
];
const COACH_FOCUS_TERMS = [
  "开放性问题",
  "具体例子",
  "项目证据",
  "结果数据",
  "复盘结论",
  "量化表达",
];

function CoachHighlightedText({ text }: { text: string }) {
  const termPattern = [...COACH_WARNING_TERMS, ...COACH_FOCUS_TERMS]
    .map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");
  const highlightPattern = new RegExp(
    `([0-9]+|[一二三四五六七八九十百千万两]+)\\s*(场|次|个|轮|题|分)|${termPattern}`,
    "g",
  );
  const nodes: React.ReactNode[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(highlightPattern)) {
    if (match.index === undefined) continue;
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    const matchedText = match[0];
    const isWarning =
      match[1] !== undefined || COACH_WARNING_TERMS.includes(matchedText);
    nodes.push(
      <span
        key={`${matchedText}-${match.index}`}
        className={isWarning ? WARNING_EMPHASIS_CLASS : EMPHASIS_CLASS}
      >
        {matchedText}
      </span>,
    );
    lastIndex = match.index + matchedText.length;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return <>{nodes}</>;
}

function CoachOpeningCopy({
  coachMessage,
  isOpeningLoading,
  fallbackUserState,
  fallbackSessionCount,
}: {
  coachMessage: CoachOpeningMessageResponse | null;
  isOpeningLoading: boolean;
  fallbackUserState: "returning" | "new";
  fallbackSessionCount: number;
}) {
  if (isOpeningLoading) {
    return (
      <div className="space-y-3.5 animate-pulse">
        <div className="h-5 w-3/4 rounded-md bg-[#e8e7e2]" />
        <div className="h-5 w-full rounded-md bg-[#e8e7e2]" />
      </div>
    );
  }
  const unifyMessage = (text: string | null) =>
    text?.replace(/(\d+)\s*场/, `${fallbackSessionCount} 场`);
  if (coachMessage) {
    return (
      <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
        <p>
          <CoachHighlightedText
            text={unifyMessage(coachMessage.greeting) || ""}
          />
        </p>
        {coachMessage.weakness_summary && (
          <p className="mt-3.5">
            <CoachHighlightedText
              text={unifyMessage(coachMessage.weakness_summary) || ""}
            />
          </p>
        )}
        {coachMessage.evidence && (
          <p className="mt-3.5">
            <CoachHighlightedText
              text={unifyMessage(coachMessage.evidence) || ""}
            />
          </p>
        )}
        <p className="mt-3.5">
          <CoachHighlightedText
            text={unifyMessage(coachMessage.focus_today) || ""}
          />
        </p>
      </div>
    );
  }
  return (
    <p>
      {fallbackUserState === "returning"
        ? "欢迎回来。"
        : "你好，我是你的 AI 面试教练。"}
    </p>
  );
}

function CoachPlanCard({
  plan,
  onStart,
}: {
  plan: CoachPlanData;
  onStart: () => void;
}) {
  return (
    <Card className="my-4 p-5 border-[#7c3aed]/20 rounded-2xl bg-gradient-to-br from-[#f5f3ff] to-white shadow-md animate-in zoom-in-95 duration-500">
      <div className="text-[10px] font-extrabold tracking-[0.12em] uppercase text-[#7c3aed] mb-2">
        教练训练计划
      </div>
      <div className="font-[var(--mac-font-display)] text-lg text-[#171717] mb-3">
        {plan.summary}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <div className="text-[11px] font-bold text-[#059669] mb-1.5">
            核心亮点
          </div>
          <ul className="space-y-1">
            {plan.strengths.slice(0, 3).map((s, i) => (
              <li key={i} className="text-xs text-[#525252] flex gap-2">
                <span>•</span> {s}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="text-[11px] font-bold text-[#e11d48] mb-1.5">
            关键短板
          </div>
          <ul className="space-y-1">
            {plan.weaknesses.slice(0, 3).map((w, i) => (
              <li key={i} className="text-xs text-[#525252] flex gap-2">
                <span>•</span> {w}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="mt-4 pt-4 border-t border-[#7c3aed]/10">
        <div className="text-[11px] font-bold text-[#4f46e5] mb-2">
          下次重点练习
        </div>
        <div className="flex flex-wrap gap-2">
          {plan.next_focus_areas.map((f, i) => (
            <span
              key={i}
              className="px-2.5 py-1 bg-[#eef2ff] text-[#4f46e5] text-[10px] font-semibold rounded-lg"
            >
              {f}
            </span>
          ))}
        </div>
      </div>
      <button
        onClick={onStart}
        className="mt-5 w-full py-3 bg-[#171717] text-white text-sm font-semibold rounded-xl hover:bg-black transition-all shadow-sm active:scale-[0.98]"
      >
        按此计划开始面试 →
      </button>
    </Card>
  );
}

function MemorySessionCard({
  session,
  onClick,
}: {
  session: MemorySession;
  onClick: () => void;
}) {
  const getScoreColor = (score: number) => {
    if (score >= 8) return "text-[#059669]";
    if (score >= 6) return "text-[#6366f1]";
    return "text-[#f43f5e]";
  };

  const getDimensionColor = (score: number) => {
    if (score >= 8) return "bg-[#059669]";
    if (score >= 6) return "bg-[#6366f1]";
    return "bg-[#f43f5e]";
  };

  // 综合诊断建议
  const getVerdict = () => {
    if (session.improvements.length > 0) {
      return session.improvements[0];
    }
    if (session.score >= 8) return "表现卓越，保持当前节奏。";
    return "整体平稳，建议深化技术细节。";
  };

  return (
    <button
      onClick={onClick}
      className="group relative flex flex-col rounded-[24px] border border-[#e2e8f0] bg-white p-0 text-left transition-all hover:border-[#6366f1]/40 hover:shadow-[0_20px_40px_-15px_rgba(0,0,0,0.08)] active:scale-[0.99] overflow-hidden"
    >
      {/* 顶部装饰条 */}
      <div
        className={`h-1.5 w-full ${session.score >= 7 ? "bg-gradient-to-r from-[#6366f1] to-[#a855f7]" : "bg-gradient-to-r from-[#f43f5e] to-[#fb923c]"}`}
      />

      <div className="p-5 flex flex-col h-full">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <div className="px-2 py-0.5 rounded-md bg-[#f8fafc] border border-[#f1f5f9] text-[9px] font-bold text-[#64748b] tracking-wider uppercase">
              SESSION #{session.sessionIndex}
            </div>
            <div className="text-[10px] font-medium text-[#94a3b8]">
              {session.date}
            </div>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#f1f5f9] text-[9px] font-bold text-[#475569]">
            <Star className="w-2.5 h-2.5 fill-[#475569]" />
            {session.targetRole}
          </div>
        </div>

        <div className="flex gap-6 mb-6">
          {/* 左侧：大分数值 */}
          <div className="flex flex-col">
            <div className="text-[10px] font-black text-[#94a3b8] uppercase tracking-tighter mb-1">
              Overall
            </div>
            <div
              className={`font-[var(--mac-font-display)] text-5xl font-black leading-none tracking-tighter ${getScoreColor(session.score)}`}
            >
              {session.score.toFixed(1)}
            </div>
          </div>

          {/* 右侧：维度条 */}
          <div className="flex-1 space-y-2.5">
            {session.dimensions.map((dim, i) => (
              <div key={i} className="space-y-1">
                <div className="flex justify-between text-[8px] font-bold text-[#64748b] uppercase tracking-wide">
                  <span>{dim.label}</span>
                  <span>{dim.score.toFixed(1)}</span>
                </div>
                <div className="h-1 w-full bg-[#f1f5f9] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-1000 ${getDimensionColor(dim.score)}`}
                    style={{ width: `${dim.score * 10}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 底部：教练诊断 */}
        <div className="mt-auto pt-4 border-t border-[#f1f5f9]">
          <div className="flex items-start gap-2.5">
            <div className="w-5 h-5 rounded-full bg-[#f1f5f9] flex items-center justify-center shrink-0">
              <BrainCircuit className="w-3 h-3 text-[#6366f1]" />
            </div>
            <div className="space-y-0.5">
              <div className="text-[9px] font-bold text-[#94a3b8] uppercase">
                Coach Diagnosis
              </div>
              <div className="text-xs font-semibold text-[#1e293b] leading-tight line-clamp-2">
                {getVerdict()}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 隐约的背景水印 */}
      <div className="absolute top-10 right-0 pointer-events-none select-none opacity-[0.03] rotate-12">
        <div className="font-[var(--mac-font-display)] text-9xl font-black">
          {session.score.toFixed(0)}
        </div>
      </div>
    </button>
  );
}

export function CoachDashboard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isLoaded, isSignedIn, getToken } = useAuth();

  const [isLoading, setIsLoading] = useState(true);
  const [stage, setStage] = useState<UserStage>("prepare");
  const [contextData, setContextData] = useState<UserContextResponse | null>(
    null,
  );
  const [coachMessage, setCoachMessage] =
    useState<CoachOpeningMessageResponse | null>(null);
  const [latestPlan, setLatestPlan] = useState<CoachPlanData | null>(null);
  const [memorySessions, setMemorySessions] = useState<MemorySession[]>([]);
  const [useQABank, setUseQABank] = useState(false);

  const [reviewText, setReviewText] = useState("");
  const [isReviewing, setIsReviewing] = useState(false);
  const [isReviewStarted, setIsReviewStarted] = useState(false);
  const [streamingPlan, setStreamingPlan] = useState<CoachPlanData | null>(
    null,
  );

  const [loadError, setLoadError] = useState(false);
  const [isRedirecting, setIsRedirecting] = useState(false);

  const reviewAbortRef = useRef<AbortController | null>(null);

  // 组件卸载时终止正在进行的复盘请求
  useEffect(() => {
    return () => {
      reviewAbortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const shouldProceed = isDevAuthBypassEnabled || (isLoaded && isSignedIn);
    if (!shouldProceed) return;
    const tokenPromise = isDevAuthBypassEnabled
      ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN)
      : getToken();

    void tokenPromise.then(async (token) => {
      if (!token) {
        setLoadError(true);
        setIsLoading(false);
        return;
      }
      try {
        const results = await Promise.allSettled([
          fetchUserStage({ token }),
          fetchInterviewContext({ token }),
          fetchInterviewHistory({ token, limit: 10 }),
          fetchLatestCoachPlan({ token }),
        ]);

        // 所有请求全部失败 = 后端不可达
        if (results.every((r) => r.status === "rejected")) {
          setLoadError(true);
          setIsLoading(false);
          return;
        }

        const [stageResult, contextResult, historyResult, planResult] = results;

        if (stageResult.status === "fulfilled") {
          setStage(stageResult.value);
        }

        if (contextResult.status === "fulfilled") {
          const context = contextResult.value;
          setContextData(context);

          if (!context.resume_filename) {
            setIsRedirecting(true);
            router.replace("/settings?require_resume=1");
            return;
          }
        }

        if (planResult.status === "fulfilled") {
          setLatestPlan(planResult.value?.plan_json || null);
        }

        if (historyResult.status === "fulfilled") {
          setMemorySessions(
            historyResult.value.sessions.map((s, idx, arr) =>
              mapHistoryItemToSession(s, idx, arr.length),
            ),
          );
        }

        setIsLoading(false);

        if (
          stageResult.status === "fulfilled" &&
          stageResult.value !== "coach"
        ) {
          try {
            const opening = await fetchCoachOpeningMessage({ token });
            setCoachMessage(opening);
          } catch {
            // coach opening message 非关键，失败静默忽略
          }
        }
      } catch (err) {
        console.error("Init failed", err);
        setLoadError(true);
      }
    });
  }, [isLoaded, isSignedIn]);

  const startCoachReviewStream = async () => {
    const token = isDevAuthBypassEnabled
      ? DEV_AUTH_BYPASS_TOKEN
      : await getToken();
    const sessionId = contextData?.last_session_id;
    if (!token || !sessionId) return;

    // 终止之前的请求
    reviewAbortRef.current?.abort();
    const controller = new AbortController();
    reviewAbortRef.current = controller;

    setIsReviewStarted(true);
    setIsReviewing(true);
    setReviewText("");

    try {
      const baseUrl = "";
      const response = await fetch(
        `${baseUrl}/api/v1/coach/review?session_id=${sessionId}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        },
      );

      if (!response.ok || !response.body) {
        throw new Error(`复盘请求失败 (${response.status})`);
      }

      await readSseStream({
        stream: response.body,
        onEvent: ({ event, data }) => {
          if (!data) return;
          if (event === "error") {
            let message = "复盘失败";
            try {
              message =
                (JSON.parse(data) as { message?: string }).message || message;
            } catch {
              /**/
            }
            throw new Error(message);
          }
          try {
            const payload = JSON.parse(data);
            if (event === "review_token")
              setReviewText((prev) => prev + payload.token);
            else if (event === "plan_done") setStreamingPlan(payload);
            else if (event === "final") setIsReviewing(false);
          } catch (e) {
            console.warn("Parse SSE error", e);
          }
        },
      });
    } catch (err) {
      if ((err as Error)?.name !== "AbortError") {
        console.error("Coach review stream error", err);
      }
    } finally {
      // 如果不是因为主动 abort 导致的结束，则关闭 loading
      if (reviewAbortRef.current === controller) {
        setIsReviewing(false);
      }
    }
  };

  const handleStartInterview = async (
    planContext?: CoachPlanData,
    customRole?: string,
  ) => {
    let userBg = "";
    if (planContext)
      userBg = `上次面试建议：${planContext.summary}。本次重点练习：${planContext.next_focus_areas.join("、")}。`;
    const targetRole =
      customRole ||
      planContext?.recommended_role ||
      contextData?.target_role ||
      "";

    await enterInterviewRoom({
      getToken: () =>
        isDevAuthBypassEnabled
          ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN)
          : getToken(),
      router,
      context: {
        target_role: targetRole,
        user_background: userBg || undefined,
        use_qa_bank: useQABank,
      },
    });
  };

  const handlePracticeMemory = async (session: MemorySession) => {
    const userBackground = `我想围绕「${session.topic}」再练一场，重点补齐：${session.improvements
      .slice(0, 2)
      .join("；")}`;
    await enterInterviewRoom({
      getToken: () =>
        isDevAuthBypassEnabled
          ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN)
          : getToken(),
      router,
      context: {
        target_role: session.targetRole,
        user_background: userBackground,
        use_qa_bank: useQABank,
      },
    });
  };

  return (
    <div className="w-full max-w-[760px] mx-auto flex flex-col gap-7 py-6 px-4 md:px-0">
      {isLoading ? (
        <div
          data-testid="coach-skeleton"
          className="animate-pulse space-y-4 py-6"
        >
          <div className="h-6 w-48 rounded bg-[#e8e7e2]" />
          <div className="h-20 w-full rounded bg-[#e8e7e2]" />
        </div>
      ) : loadError ? (
        <div className="flex flex-col items-center justify-center py-16 gap-4">
          <div className="text-sm text-[#8a8a8a]">无法连接到后端服务</div>
          <p className="text-xs text-[#a3a3a3] max-w-xs text-center">
            请确认后端已启动（
            <code className="bg-[#f1f5f9] px-1 rounded">bash dev.sh</code>
            ），然后刷新页面重试。
          </p>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-3.5 pb-4 border-b border-[#e8e7e2]">
            <div className="relative flex-shrink-0">
              <div className="w-[52px] h-[52px] rounded-full bg-gradient-to-br from-[#7c3aed] to-[#4f46e5] text-white flex items-center justify-center font-[var(--mac-font-display)] text-[22px] font-normal shadow-lg ring-4 ring-[#7c3aed]/10">
                C
              </div>
              <span className="absolute -right-0.5 -bottom-0.5 w-3.5 h-3.5 rounded-full bg-[#059669] border-2 border-white shadow-sm animate-pulse" />
            </div>
            <div>
              <div className="font-bold text-xl text-[#171717]">Coach</div>
              <div className="text-xs text-[#8a8a8a] mt-0.5">
                你的 AI 面试教练 · 已陪你 {contextData?.session_count ?? 0} 场
                {contextData?.target_role &&
                  ` · 当前练习岗位：${contextData.target_role}`}
              </div>
            </div>
          </div>

          <div className="flex gap-4">
            <div className="w-[2px] shrink-0 rounded bg-gradient-to-b from-[#7c3aed] to-[#4f46e5] opacity-40" />
            <div className="flex-1">
              {stage === "coach" && (
                <div className="animate-in fade-in duration-700">
                  {!isReviewStarted ? (
                    <div className="p-10 text-center rounded-3xl bg-[#faf9f5] border border-[#e8e7e2] shadow-sm">
                      <h3 className="text-2xl font-bold mb-4 text-[#171717]">
                        面试已圆满结束
                      </h3>
                      <p className="text-[#525252] mb-8 leading-relaxed">
                        恭喜你完成本轮面试练习！点击下方按钮，即可根据你的历史表现开始新一轮的针对性练习。
                      </p>
                      <Button
                        onClick={() => handleStartInterview()}
                        className="bg-gradient-to-br from-[#7c3aed] to-[#4f46e5] text-white px-10 py-7 text-lg rounded-2xl hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl font-bold"
                      >
                        开始面试练习 →
                      </Button>
                    </div>
                  ) : (
                    <>
                      <div className="text-xl md:text-2xl leading-relaxed text-[#171717] whitespace-pre-wrap font-medium">
                        <CoachHighlightedText
                          text={
                            reviewText ||
                            (isReviewing ? "正在进行面试诊断..." : "")
                          }
                        />
                      </div>
                      {streamingPlan && (
                        <div className="mt-8">
                          <CoachPlanCard
                            plan={streamingPlan}
                            onStart={() => handleStartInterview(streamingPlan)}
                          />
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {stage === "prepare" && (
                <div className="animate-in fade-in duration-700">
                  <CoachOpeningCopy
                    coachMessage={coachMessage}
                    isOpeningLoading={false}
                    fallbackUserState={
                      contextData?.is_returning ? "returning" : "new"
                    }
                    fallbackSessionCount={contextData?.session_count ?? 0}
                  />

                  {latestPlan && (
                    <div className="mt-10 pt-8 border-t border-dashed border-[#e8e7e2]">
                      <div className="text-[10px] font-bold text-[#8a8a8a] uppercase tracking-widest mb-4">
                        上次复盘建议
                      </div>
                      <CoachPlanCard
                        plan={latestPlan}
                        onStart={() => handleStartInterview(latestPlan)}
                      />
                    </div>
                  )}

                  {!latestPlan && contextData?.target_role ? (
                    <div className="mt-8 flex gap-3 flex-wrap">
                      <button
                        onClick={() => handleStartInterview()}
                        className="px-6 py-3.5 bg-[#171717] text-white rounded-2xl font-semibold text-sm shadow-xl hover:bg-black transition-all"
                      >
                        直接开始面试
                      </button>
                      <button
                        onClick={() => router.push("/settings")}
                        className="px-6 py-3.5 bg-white border border-[#dcdbd5] text-[#525252] rounded-2xl font-semibold text-sm hover:border-[#b8b5aa] transition-all"
                      >
                        调整面试目标
                      </button>
                    </div>
                  ) : latestPlan ? (
                    <div className="mt-8">
                      <div className="flex gap-3 flex-wrap">
                        <button
                          onClick={() => handleStartInterview()}
                          className="px-6 py-3.5 bg-[#171717] text-white rounded-2xl font-semibold text-sm shadow-xl hover:bg-black transition-all"
                        >
                          常规开始一场面试
                        </button>
                        <button
                          onClick={() => router.push("/settings")}
                          className="px-6 py-3.5 bg-white border border-[#dcdbd5] text-[#525252] rounded-2xl font-semibold text-sm hover:border-[#b8b5aa] transition-all"
                        >
                          调整面试目标
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-8 flex gap-3 flex-wrap">
                      <button
                        onClick={() => handleStartInterview()}
                        className="px-6 py-3.5 bg-[#171717] text-white rounded-2xl font-semibold text-sm shadow-xl hover:bg-black transition-all"
                      >
                        直接开始面试
                      </button>
                      <button
                        onClick={() => router.push("/settings")}
                        className="px-6 py-3.5 bg-white border border-[#dcdbd5] text-[#525252] rounded-2xl font-semibold text-sm hover:border-[#b8b5aa] transition-all"
                      >
                        调整面试目标
                      </button>
                    </div>
                  )}
                </div>
              )}

              {stage === "interview" && (
                <div className="p-10 text-center rounded-3xl bg-[#faf9f5] border border-[#e8e7e2] shadow-sm animate-in zoom-in-95 duration-500">
                  <h3 className="text-2xl font-bold mb-4 text-[#171717]">
                    {contextData?.target_role
                      ? `${contextData.target_role} 面试正在进行中`
                      : "面试正在进行中"}
                  </h3>
                  <p className="text-[#525252] mb-8 leading-relaxed">
                    你有一场尚未结束的 {contextData?.target_role || "模拟"}{" "}
                    面试，你的 AI 面试教练已经准备好陪你继续练习。
                  </p>
                  <Button
                    onClick={() => router.push("/interview")}
                    className="bg-[#171717] text-white px-10 py-7 text-lg rounded-2xl hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl"
                  >
                    立即返回面试间
                  </Button>
                </div>
              )}
            </div>
          </div>

          <div className="mt-12 pt-8 border-t border-[#e8e7e2]">
            <div className="flex items-end justify-between mb-6">
              <div className="text-[10px] font-extrabold uppercase tracking-[0.15em] text-[#8a8a8a]">
                近期面试记忆
              </div>
              <Link
                href="/dashboard"
                className="text-xs font-bold text-[#4f46e5] hover:underline"
              >
                查看完整历史 →
              </Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {memorySessions.slice(0, 4).map((s) => (
                <MemorySessionCard
                  key={s.id}
                  session={s}
                  onClick={() => handlePracticeMemory(s)}
                />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
