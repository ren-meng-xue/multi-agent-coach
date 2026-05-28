"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@clerk/nextjs";
import {
  fetchCoachOpeningMessage,
  fetchInterviewContext,
  fetchInterviewHistory,
  enterInterviewRoom,
  type CoachOpeningMessageResponse,
  type UserContextResponse,
  type InterviewHistoryItem,
} from "@/lib/interview-chat";
import { updateUserProfile } from "@/lib/user";
import { 
  fetchUserStage, 
  fetchLatestCoachPlan, 
  type UserStage, 
  type CoachPlanData 
} from "@/lib/coach";

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
function mapHistoryItemToSession(item: InterviewHistoryItem, index: number, total: number): MemorySession {
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
const EMPHASIS_CLASS = "text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans";
const WARNING_EMPHASIS_CLASS = "text-[#e11d48] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(225,29,72,0.16)_62%)] font-sans";
const COACH_WARNING_TERMS = ["缺少具体例证", "缺乏具体实例", "不够具体", "缺少量化", "缺乏量化", "说服力"];
const COACH_FOCUS_TERMS = ["开放性问题", "具体例子", "项目证据", "结果数据", "复盘结论", "量化表达"];

function CoachHighlightedText({ text }: { text: string }) {
  const termPattern = [...COACH_WARNING_TERMS, ...COACH_FOCUS_TERMS]
    .map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");
  const highlightPattern = new RegExp(`([0-9]+|[一二三四五六七八九十百千万两]+)\\s*(场|次|个|轮|题|分)|${termPattern}`, "g");
  const nodes: React.ReactNode[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(highlightPattern)) {
    if (match.index === undefined) continue;
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    const matchedText = match[0];
    const isWarning = match[1] !== undefined || COACH_WARNING_TERMS.includes(matchedText);
    nodes.push(<span key={`${matchedText}-${match.index}`} className={isWarning ? WARNING_EMPHASIS_CLASS : EMPHASIS_CLASS}>{matchedText}</span>);
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
  const unifyMessage = (text: string | null) => text?.replace(/(\d+)\s*场/, `${fallbackSessionCount} 场`);
  if (coachMessage) {
    return (
      <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
        <p><CoachHighlightedText text={unifyMessage(coachMessage.greeting) || ""} /></p>
        {coachMessage.weakness_summary && <p className="mt-3.5"><CoachHighlightedText text={unifyMessage(coachMessage.weakness_summary) || ""} /></p>}
        {coachMessage.evidence && <p className="mt-3.5"><CoachHighlightedText text={unifyMessage(coachMessage.evidence) || ""} /></p>}
        <p className="mt-3.5"><CoachHighlightedText text={unifyMessage(coachMessage.focus_today) || ""} /></p>
      </div>
    );
  }
  return <p>{fallbackUserState === "returning" ? "欢迎回来。" : "你好，我是你的 AI 面试教练。"}</p>;
}

function CoachPlanCard({ plan, onStart }: { plan: CoachPlanData; onStart: () => void }) {
  return (
    <Card className="my-4 p-5 border-[#7c3aed]/20 rounded-2xl bg-gradient-to-br from-[#f5f3ff] to-white shadow-md animate-in zoom-in-95 duration-500">
      <div className="text-[10px] font-extrabold tracking-[0.12em] uppercase text-[#7c3aed] mb-2">教练训练计划</div>
      <div className="font-[var(--mac-font-display)] text-lg text-[#171717] mb-3">{plan.summary}</div>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <div className="text-[11px] font-bold text-[#059669] mb-1.5">核心亮点</div>
          <ul className="space-y-1">
            {plan.strengths.slice(0, 3).map((s, i) => <li key={i} className="text-xs text-[#525252] flex gap-2"><span>•</span> {s}</li>)}
          </ul>
        </div>
        <div>
          <div className="text-[11px] font-bold text-[#e11d48] mb-1.5">关键短板</div>
          <ul className="space-y-1">
            {plan.weaknesses.slice(0, 3).map((w, i) => <li key={i} className="text-xs text-[#525252] flex gap-2"><span>•</span> {w}</li>)}
          </ul>
        </div>
      </div>
      <div className="mt-4 pt-4 border-t border-[#7c3aed]/10">
        <div className="text-[11px] font-bold text-[#4f46e5] mb-2">下次重点练习</div>
        <div className="flex flex-wrap gap-2">
          {plan.next_focus_areas.map((f, i) => (
            <span key={i} className="px-2.5 py-1 bg-[#eef2ff] text-[#4f46e5] text-[10px] font-semibold rounded-lg">{f}</span>
          ))}
        </div>
      </div>
      <button onClick={onStart} className="mt-5 w-full py-3 bg-[#171717] text-white text-sm font-semibold rounded-xl hover:bg-black transition-all shadow-sm active:scale-[0.98]">
        按此计划开始面试 →
      </button>
    </Card>
  );
}

function MemorySessionCard({ session, onClick }: { session: MemorySession; onClick: () => void }) {
  return (
    <button onClick={onClick} className="group flex flex-col rounded-2xl border border-[#e8e7e2] bg-white p-4 text-left transition-all hover:border-[#c9c6bc] hover:shadow-md">
      <div className="text-[11px] font-semibold text-[#8a8a8a]">第 {session.sessionIndex} 场 · {session.date}</div>
      <div className="mt-2 font-bold text-sm text-[#171717] line-clamp-1">{session.topic}</div>
      <div className="mt-4 flex items-end justify-between">
        <div className="font-[var(--mac-font-display)] text-[28px] font-bold leading-none">{session.score.toFixed(1)}</div>
        <div className="text-[10px] px-2 py-0.5 rounded-full bg-[#faf9f5] border border-[#e8e7e2] text-[#525252]">{session.targetRole}</div>
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
  const [contextData, setContextData] = useState<UserContextResponse | null>(null);
  const [coachMessage, setCoachMessage] = useState<CoachOpeningMessageResponse | null>(null);
  const [latestPlan, setLatestPlan] = useState<CoachPlanData | null>(null);
  const [memorySessions, setMemorySessions] = useState<MemorySession[]>([]);

  const [reviewText, setReviewText] = useState("");
  const [isReviewing, setIsReviewing] = useState(false);
  const [streamingPlan, setStreamingPlan] = useState<CoachPlanData | null>(null);

  const [inputText, setInputText] = useState("");
  const [userMessage, setUserMessage] = useState<string | null>(null);
  const [speechStage, setSpeechStage] = useState<"initial" | "follow" | "custom-reply">("initial");

  useEffect(() => {
    if (!isLoaded || (!isSignedIn && !isDevAuthBypassEnabled)) return;
    const tokenPromise = isDevAuthBypassEnabled ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN) : getToken();

    void tokenPromise.then(async (token) => {
      if (!token) return;
      try {
        const [stageVal, context, history, plan] = await Promise.all([
          fetchUserStage({ token }),
          fetchInterviewContext({ token }),
          fetchInterviewHistory({ token, limit: 10 }),
          fetchLatestCoachPlan({ token }),
        ]);

        setStage(stageVal);
        setContextData(context);
        setLatestPlan(plan?.plan_json || null);
        setMemorySessions(history.sessions.map((s, idx, arr) => mapHistoryItemToSession(s, idx, arr.length)));
        setIsLoading(false);

        if (stageVal === "coach" && context.last_session_id) {
          void startCoachReviewStream(token, context.last_session_id);
        } else {
          const opening = await fetchCoachOpeningMessage({ token });
          setCoachMessage(opening);
        }
      } catch (err) {
        console.error("Init failed", err);
        setIsLoading(false);
      }
    });
  }, [isLoaded, isSignedIn]);

  const startCoachReviewStream = async (token: string, sessionId: string) => {
    setIsReviewing(true);
    setReviewText("");
    const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "";
    const response = await fetch(`${baseUrl}/api/v1/coach/review?session_id=${sessionId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        if (!chunk.startsWith("event: ")) continue;
        const lines = chunk.split("\n");
        const eventName = lines[0].replace("event: ", "").trim();
        const dataStr = lines[1].replace("data: ", "").trim();
        try {
          const data = JSON.parse(dataStr);
          if (eventName === "review_token") setReviewText(prev => prev + data.token);
          else if (eventName === "plan_done") setStreamingPlan(data);
          else if (eventName === "final") setIsReviewing(false);
        } catch (e) { console.warn("Parse SSE error", e); }
      }
    }
  };

  const handleStartInterview = async (planContext?: CoachPlanData) => {
    let userBg = "";
    if (planContext) userBg = `上次面试建议：${planContext.summary}。本次重点练习：${planContext.next_focus_areas.join("、")}。`;
    await enterInterviewRoom({
      getToken: () => isDevAuthBypassEnabled ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN) : getToken(),
      router,
      context: { target_role: planContext?.recommended_role || contextData?.target_role || "", user_background: userBg || undefined },
    });
  };

  return (
    <div className="w-full max-w-[760px] mx-auto flex flex-col gap-7 py-6 px-4 md:px-0">
      {isLoading ? (
        <div data-testid="coach-skeleton" className="animate-pulse space-y-4 py-6">
          <div className="h-6 w-48 rounded bg-[#e8e7e2]" />
          <div className="h-20 w-full rounded bg-[#e8e7e2]" />
        </div>
      ) : (

        <>
          <div className="flex items-center gap-3.5 pb-4 border-b border-[#e8e7e2]">
            <div className="w-[52px] h-[52px] rounded-full bg-gradient-to-br from-[#7c3aed] to-[#4f46e5] text-white flex items-center justify-center font-bold text-xl shadow-lg">C</div>
            <div>
              <div className="font-bold text-xl text-[#171717]">Coach</div>
              <div className="text-xs text-[#8a8a8a] mt-0.5">你的 AI 面试教练 · 已陪你 {contextData?.session_count ?? 0} 场</div>
            </div>
          </div>

          <div className="flex gap-4">
            <div className="w-[2px] shrink-0 rounded bg-gradient-to-b from-[#7c3aed] to-[#4f46e5] opacity-40" />
            <div className="flex-1">
              
              {stage === "coach" && (
                <div className="animate-in fade-in duration-700">
                  <div className="text-xl md:text-2xl leading-relaxed text-[#171717] whitespace-pre-wrap font-medium">
                    <CoachHighlightedText text={reviewText || (isReviewing ? "正在深度复盘本次面试..." : "")} />
                  </div>
                  {streamingPlan && <div className="mt-8"><CoachPlanCard plan={streamingPlan} onStart={() => handleStartInterview(streamingPlan)} /></div>}
                </div>
              )}

              {stage === "prepare" && (
                <div className="animate-in fade-in duration-700">
                  <CoachOpeningCopy coachMessage={coachMessage} isOpeningLoading={false} fallbackUserState={contextData?.is_returning ? "returning" : "new"} fallbackSessionCount={contextData?.session_count ?? 0} />
                  {latestPlan && (
                    <div className="mt-10 pt-8 border-t border-dashed border-[#e8e7e2]">
                      <div className="text-[10px] font-bold text-[#8a8a8a] uppercase tracking-widest mb-4">上次复盘建议</div>
                      <CoachPlanCard plan={latestPlan} onStart={() => handleStartInterview(latestPlan)} />
                    </div>
                  )}
                  <div className="mt-8 flex gap-3 flex-wrap">
                    <button onClick={() => handleStartInterview()} className="px-6 py-3.5 bg-[#171717] text-white rounded-2xl font-semibold text-sm shadow-xl hover:bg-black transition-all">常规开始一场面试</button>
                    <button onClick={() => router.push("/settings")} className="px-6 py-3.5 bg-white border border-[#dcdbd5] text-[#525252] rounded-2xl font-semibold text-sm hover:border-[#b8b5aa] transition-all">调整面试目标</button>
                  </div>
                </div>
              )}

              {stage === "interview" && (
                <div className="p-10 text-center rounded-3xl bg-[#faf9f5] border border-[#e8e7e2] shadow-sm animate-in zoom-in-95 duration-500">
                  <h3 className="text-2xl font-bold mb-4 text-[#171717]">面试正在进行中</h3>
                  <p className="text-[#525252] mb-8 leading-relaxed">你有一场尚未结束的面试，专家委员会正在等你回来。</p>
                  <Button onClick={() => router.push("/interview")} className="bg-[#171717] text-white px-10 py-7 text-lg rounded-2xl hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl">
                    立即返回面试间
                  </Button>
                </div>
              )}
            </div>
          </div>

          <div className="mt-12 pt-8 border-t border-[#e8e7e2]">
            <div className="flex items-end justify-between mb-6">
              <div className="text-[10px] font-extrabold uppercase tracking-[0.15em] text-[#8a8a8a]">近期面试记忆</div>
              <Link href="/dashboard" className="text-xs font-bold text-[#4f46e5] hover:underline">查看完整历史 →</Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {memorySessions.slice(0, 4).map(s => <MemorySessionCard key={s.id} session={s} onClick={() => router.push(`/reports?session_id=${s.id}`)} />)}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
