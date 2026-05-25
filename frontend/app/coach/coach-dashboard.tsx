"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@clerk/nextjs";
import {
  fetchCoachOpeningMessage,
  fetchInterviewContext,
  fetchInterviewHistory,
  resetInterviewSession,
  type CoachOpeningMessageResponse,
  type UserContextResponse,
  type InterviewHistoryItem,
} from "@/lib/interview-chat";
import { updateUserProfile } from "@/lib/user";

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
  
  // 维度映射
  const dimensions = [
    { label: "技术深度", score: report.technical_depth || 0 },
    { label: "量化结果", score: report.quantified_results || 0 },
    { label: "失败降级", score: report.failure_tradeoffs || 0 },
    { label: "结构表达", score: report.structure || 0 },
  ];

  // 如果没有报告数据，尝试使用基础分
  const displayScore = item.score || report.overall_score || 0;

  return {
    id: item.id,
    sessionIndex: total - index,
    date: item.date,
    topic: item.topic,
    targetRole: item.target_role,
    score: displayScore,
    passFail: item.pass_fail as "pass" | "fail" | "partial",
    trend: "flat", // 简单处理
    dimensions,
    highlights: report.highlights || [],
    improvements: report.improvements || item.key_issues || [],
    keyConcepts: report.key_concepts || [],
    commonMistakes: report.common_mistakes || [],
  };
}

const COACH_MEMORY_PREVIEW_LIMIT = 2;
const DEV_AUTH_BYPASS_TOKEN = "dev-auth-bypass-token";
const isDevAuthBypassEnabled = process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "1";
const EMPHASIS_CLASS =
  "text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans";
const WARNING_EMPHASIS_CLASS =
  "text-[#e11d48] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(225,29,72,0.16)_62%)] font-sans";
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
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    const matchedText = match[0];
    const isWarning = match[1] !== undefined || COACH_WARNING_TERMS.includes(matchedText);
    nodes.push(
      <span key={`${matchedText}-${match.index}`} className={isWarning ? WARNING_EMPHASIS_CLASS : EMPHASIS_CLASS}>
        {matchedText}
      </span>,
    );
    lastIndex = match.index + matchedText.length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return <>{nodes}</>;
}

function CoachOpeningCopy({
  coachMessage,
  fallbackUserState,
  fallbackSessionCount,
}: {
  coachMessage: CoachOpeningMessageResponse | null;
  fallbackUserState: "returning" | "new";
  fallbackSessionCount: number;
}) {
  // 统一数据：如果 LLM 返回的文案中包含错误的场次数字，强制替换为真实场次以保持一致性。
  const unifyMessage = (text: string | null) => {
    if (!text) return null;
    // 匹配类似 "22 场" 或 "22场" 的模式，并替换为真实场次
    return text.replace(/(\d+)\s*场/, `${fallbackSessionCount} 场`);
  };

  if (coachMessage) {
    return (
      <div>
        <p>
          <CoachHighlightedText text={unifyMessage(coachMessage.greeting) || ""} />
        </p>
        {coachMessage.weakness_summary && (
          <p className="mt-3.5">
            <CoachHighlightedText text={unifyMessage(coachMessage.weakness_summary) || ""} />
          </p>
        )}
        {coachMessage.evidence && (
          <p className="mt-3.5">
            <CoachHighlightedText text={unifyMessage(coachMessage.evidence) || ""} />
          </p>
        )}
        <p className="mt-3.5">
          <CoachHighlightedText text={unifyMessage(coachMessage.focus_today) || ""} />
        </p>
      </div>
    );
  }

  if (fallbackUserState === "returning") {
    return (
      <div>
        <p>欢迎回来。</p>
        <p className="mt-3.5">
          我看了你过去 {fallbackSessionCount} 场面试，发现一个挺要命的规律 ——<br />
          你讲项目时，<span className={WARNING_EMPHASIS_CLASS}>结果指标永远是模糊的</span>，7 场里有{" "}
          <span className={WARNING_EMPHASIS_CLASS}>5 场</span> 都被扣。
        </p>
        <p className="mt-3.5">
          今天我想让你重练，<span className={EMPHASIS_CLASS}>这次你必须给我数字</span>。
        </p>
      </div>
    );
  }

  return (
    <div>
      <p>你好。我还不认识你。</p>
      <p className="mt-3.5">
        我是你的 AI 面试教练 —— 我会陪你练面试，记住你讲过的每个项目，<br />
        然后告诉你 <span className={EMPHASIS_CLASS}>下次该怎么讲会更好</span>。
      </p>
      <p className="mt-3.5">
        开始之前，先告诉我：你正在准备 <span className={EMPHASIS_CLASS}>什么岗位</span>？
      </p>
    </div>
  );
}

function trendLabel(trend: MemorySession["trend"]) {
  if (trend === "up") return "↗";
  if (trend === "down") return "↘";
  return "→";
}

function MemorySessionCard({
  session,
  onClick,
}: {
  session: MemorySession;
  onClick: () => void;
}) {
  const isPass = session.passFail === "pass";
  const isPartial = session.passFail === "partial";
  const trendColor =
    session.trend === "up"
      ? "text-[#059669]"
      : session.trend === "down"
      ? "text-[#e11d48]"
      : "text-[#8a8a8a]";

  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex h-full min-h-[258px] flex-col rounded-2xl border border-[#e8e7e2] bg-white p-4 text-left shadow-[0_1px_0_rgba(23,23,23,0.03)] transition-all hover:-translate-y-0.5 hover:border-[#c9c6bc] hover:shadow-[0_14px_34px_rgba(23,23,23,0.08)] focus:outline-none focus:ring-2 focus:ring-[#7c3aed]/30"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold text-[#8a8a8a]">
            第 {session.sessionIndex} 场 · {session.date}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {session.topic.split(" · ").map((tag, index) => (
              <span
                key={`${session.id}-${tag}`}
                className={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                  index === 0
                    ? "bg-[#eef2ff] text-[#4f46e5]"
                    : "bg-[#edf7f2] text-[#047857]"
                }`}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
        <span className={`text-base font-bold ${trendColor}`}>{trendLabel(session.trend)}</span>
      </div>

      <div className="mt-4 flex items-end justify-between gap-3">
        <div className="font-[var(--mac-font-display)] text-[34px] font-bold leading-none text-[#171717]">
          {session.score.toFixed(1)}
        </div>
        <div
          className={`rounded-full px-2.5 py-1 text-xs font-bold ${
            isPass 
              ? "bg-[#e9f8f1] text-[#047857]" 
              : isPartial
                ? "bg-[#fef9c3] text-[#a16207]"
                : "bg-[#fff1f2] text-[#be123c]"
          }`}
        >
          {isPass ? "✓ 通过" : isPartial ? "− 待定" : "✗ 未过"}
        </div>
      </div>

      <div className="mt-4 space-y-3">
        <div>
          <div className="mb-1.5 text-[11px] font-extrabold tracking-[0.08em] text-[#4f46e5]">
            💡 核心概念
          </div>
          <div className="space-y-1">
            {session.keyConcepts.slice(0, 2).map((concept) => (
              <div key={concept} className="line-clamp-1 text-xs leading-5 text-[#525252]">
                {concept}
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-1.5 text-[11px] font-extrabold tracking-[0.08em] text-[#059669]">
            ⚠️ 待改进
          </div>
          <div className="space-y-1">
            {session.improvements.slice(0, 2).map((item) => (
              <div key={item} className="line-clamp-1 text-xs leading-5 text-[#525252]">
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-auto pt-4">
        <span className="rounded-full border border-[#dcdbd5] bg-[#faf9f5] px-2.5 py-1 text-[11px] font-semibold text-[#525252]">
          {session.targetRole}
        </span>
      </div>
    </button>
  );
}

function MemorySessionModal({
  session,
  onClose,
  onPracticeAgain,
}: {
  session: MemorySession | null;
  onClose: () => void;
  onPracticeAgain: (session: MemorySession) => void;
}) {
  // ESC 键关闭支持
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (session) {
      window.addEventListener("keydown", handleEsc);
    }
    return () => window.removeEventListener("keydown", handleEsc);
  }, [session, onClose]);

  if (!session) return null;

  const isPass = session.passFail === "pass";
  const isPartial = session.passFail === "partial";

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/35 p-3 backdrop-blur-sm md:items-center"
      onClick={onClose}
    >
      <div
        className="max-h-[88vh] w-full max-w-4xl overflow-y-auto rounded-2xl bg-white shadow-[0_24px_80px_rgba(0,0,0,0.24)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b border-[#e8e7e2] p-5 md:p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[11px] font-extrabold tracking-[0.12em] uppercase text-[#8a8a8a]">
                {session.topic} · 第 {session.sessionIndex} 场 · {session.date}
              </div>
              <h3 className="mt-2 font-[var(--mac-font-display)] text-2xl font-bold text-[#171717]">
                整场复盘
              </h3>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-[#e8e7e2] px-3 py-1.5 text-sm text-[#525252] hover:border-[#b8b5aa] hover:text-[#171717]"
            >
              关闭
            </button>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2.5">
            <span className="font-[var(--mac-font-display)] text-3xl font-bold text-[#171717]">
              {session.score.toFixed(1)}
            </span>
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-bold ${
                isPass 
                  ? "bg-[#e9f8f1] text-[#047857]" 
                  : isPartial
                    ? "bg-[#fef9c3] text-[#a16207]"
                    : "bg-[#fff1f2] text-[#be123c]"
              }`}
            >
              {isPass ? "✓ 通过" : isPartial ? "− 待定" : "✗ 未过"}
            </span>
            <span className="rounded-full border border-[#dcdbd5] bg-[#faf9f5] px-2.5 py-1 text-xs font-semibold text-[#525252]">
              {session.targetRole}
            </span>
          </div>
        </div>

        <div className="space-y-6 p-5 md:p-6">
          <section>
            <h4 className="mb-3 text-sm font-bold text-[#171717]">📊 4 维度评分</h4>
            <div className="grid gap-2 md:grid-cols-2">
              {session.dimensions.map((dimension) => (
                <div key={dimension.label} className="rounded-xl border border-[#e8e7e2] p-3">
                  <div className="flex items-center justify-between text-xs font-semibold text-[#525252]">
                    <span>{dimension.label}</span>
                    <span>{dimension.score.toFixed(1)} / 5</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#efeee8]">
                    <div
                      className="h-full rounded-full bg-[#4f46e5]"
                      style={{ width: `${Math.round((dimension.score / 5) * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <div className="grid gap-5 md:grid-cols-2">
            <MemoryList title="✅ 亮点全文" tone="green" items={session.highlights} />
            <MemoryList title="⚠️ 待改进全文" tone="rose" items={session.improvements} />
            <MemoryList title="💡 核心概念全文" tone="blue" items={session.keyConcepts} />
            <MemoryList title="🚨 常见陷阱" tone="amber" items={session.commonMistakes} />
          </div>

          <div className="flex flex-col gap-2 border-t border-[#e8e7e2] pt-5 sm:flex-row">
            <button
              type="button"
              onClick={() => onPracticeAgain(session)}
              className="rounded-2xl bg-[#171717] px-5 py-3 text-sm font-semibold text-white shadow-[0_6px_18px_rgba(23,23,23,0.18)] hover:bg-black"
            >
              按本场考点再练一场
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-2xl border border-[#dcdbd5] bg-white px-5 py-3 text-sm font-semibold text-[#525252] hover:border-[#b8b5aa] hover:text-[#171717]"
            >
              先关掉
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function MemoryList({
  title,
  tone,
  items,
}: {
  title: string;
  tone: "green" | "rose" | "blue" | "amber";
  items: string[];
}) {
  const toneClass = {
    green: "border-[#cdebdc] bg-[#f0fbf6]",
    rose: "border-[#ffd9df] bg-[#fff5f6]",
    blue: "border-[#dbe4ff] bg-[#f4f6ff]",
    amber: "border-[#ffe5b4] bg-[#fff9ec]",
  }[tone];

  return (
    <section>
      <h4 className="mb-2 text-sm font-bold text-[#171717]">{title}</h4>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item} className={`rounded-xl border p-3 text-sm leading-6 text-[#525252] ${toneClass}`}>
            {item}
          </div>
        ))}
      </div>
    </section>
  );
}

export function CoachDashboard() {
  const router = useRouter();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [contextData, setContextData] = useState<UserContextResponse | null>(null);
  const [coachMessage, setCoachMessage] = useState<CoachOpeningMessageResponse | null>(null);
  const [memorySessions, setMemorySessions] = useState<MemorySession[]>([]);

  const [isThinking, setIsThinking] = useState(false);
  const [inputText, setInputText] = useState("");
  
  // 阶段 3 新增 JD 输入状态
  const [showJdInput, setShowJdInput] = useState(false);
  const [jdText, setJdText] = useState("");
  const [jdUrl, setJdUrl] = useState("");
  
  // 聊天上下文状态机
  const [userMessage, setUserMessage] = useState<string | null>(null);
  const [speechStage, setSpeechStage] = useState<
    "initial" | "follow" | "switch" | "switch-target" | "new-role" | "custom-reply"
  >("initial");
  
  const [selectedRole, setSelectedRole] = useState("");
  const [selectedTargetLabel, setSelectedTargetLabel] = useState("");
  const [selectedMemory, setSelectedMemory] = useState<MemorySession | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // userState 兼容现有状态机，is_returning 对应 "returning"，否则 "new"
  const userState: "returning" | "new" = contextData?.is_returning ? "returning" : "new";
  const previewMemorySessions = memorySessions.slice(0, COACH_MEMORY_PREVIEW_LIMIT);

  // API 加载 effect
  useEffect(() => {
    let isCancelled = false;

    if (!isLoaded || (!isSignedIn && !isDevAuthBypassEnabled)) {
      if (isLoaded && !isSignedIn && !isDevAuthBypassEnabled) {
        setIsLoading(false);
      }
      return () => {
        isCancelled = true;
      };
    }
    
    const fetchToken = isDevAuthBypassEnabled ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN) : getToken();

    void fetchToken.then(async (token) => {
      if (!token) {
        if (!isCancelled) setIsLoading(false);
        return;
      }
      try {
        // 1. 发出核心请求：基础上下文和历史记录（阻塞骨架屏）
        const [context, history] = await Promise.all([
          fetchInterviewContext({ token }),
          fetchInterviewHistory({ token, limit: 10 }),
        ]);

        if (isCancelled) return;

        // 2. 状态批量更新
        setContextData(context);
        
        // 映射并计算趋势
        const mappedSessions = history.sessions.map((s, idx, arr) => {
          const session = mapHistoryItemToSession(s, idx, arr.length);
          // 比较相邻场次分数的简单趋势算法
          if (idx < arr.length - 1) {
            const prevSession = arr[idx + 1];
            if (s.score > prevSession.score + 0.1) session.trend = "up";
            else if (s.score < prevSession.score - 0.1) session.trend = "down";
          }
          return session;
        });
        
        setMemorySessions(mappedSessions);
        setIsLoading(false);

        // 3. 异步获取 Coach 开场词（非阻塞）
        void fetchCoachOpeningMessage({ token }).then((opening) => {
          if (!isCancelled) setCoachMessage(opening);
        }).catch((err) => {
          console.warn("fetchCoachOpeningMessage failed, using fallback:", err);
        });
      } catch (error) {
        console.error("CoachDashboard critical data fetch failed:", error);
        if (!isCancelled) setIsLoading(false);
      }
    });

    return () => {
      isCancelled = true;
    };
  }, [isLoaded, isSignedIn, getToken]);

  // 重置交互阶段
  const resetConversation = () => {
    setUserMessage(null);
    setIsThinking(false);
    setInputText("");
    setSpeechStage("initial");
    setSelectedRole("");
    setSelectedTargetLabel("");
  };

  // 处理输入框高度自适应
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 96)}px`;
    }
  }, [inputText]);

  // 发送消息交互
  const handleSend = () => {
    const text = inputText.trim();
    if (!text) return;
    
    setUserMessage(text);
    setInputText("");
    setIsThinking(true);
    
    // 1.4s 呼吸思考动效后，Coach 回应
    setTimeout(() => {
      setIsThinking(false);
      setSpeechStage("custom-reply");
    }, 1400);
  };

  // 监听回车发送
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 处理 CTA 的点击事件
  const handleAction = async (action: string, extra?: string) => {
    if (action === "follow") {
      setSpeechStage("follow");
    } else if (action === "switch") {
      setSpeechStage("switch");
    } else if (action === "switch-target" && extra) {
      setSelectedTargetLabel(extra);
      setSpeechStage("switch-target");
    } else if (action === "new-role" && extra) {
      setSelectedRole(extra);
      setUserMessage(`我在准备 ${extra} 的面试`);
      setSpeechStage("new-role");
      
      // 持久化到用户 Profile
      const fetchToken = isDevAuthBypassEnabled ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN) : getToken();
      void fetchToken.then(async (token) => {
        if (token) {
          await updateUserProfile({ token, profile: { target_role: extra } });
        }
      });
    } else if (action === "reset") {
      resetConversation();
    } else if (action === "go-room") {
      const role = selectedRole || contextData?.target_role || "";
      const bg = userMessage || contextData?.user_background || "";
      if (role) {
        sessionStorage.setItem(
          "interview_context",
          JSON.stringify({
            target_role: role,
            user_background: bg,
            jd_text: jdText,
            jd_url: jdUrl,
          }),
        );
        const fetchToken = isDevAuthBypassEnabled ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN) : getToken();
        const token = await fetchToken;
        if (token) {
          await resetInterviewSession({
            token,
            target_role: role,
            user_background: bg || undefined,
          });
        }
      }
      router.push("/interview");
    } else if (action === "go-setup") {
      router.push("/settings");
    }
  };

  const handlePracticeMemory = async (session: MemorySession) => {
    const userBackground = `我想围绕「${session.topic}」再练一场，重点补齐：${session.improvements
      .slice(0, 2)
      .join("；")}`;
    sessionStorage.setItem(
      "interview_context",
      JSON.stringify({ target_role: session.targetRole, user_background: userBackground }),
    );
    const fetchToken = isDevAuthBypassEnabled ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN) : getToken();
    const token = await fetchToken;
    if (token) {
      await resetInterviewSession({
        token,
        target_role: session.targetRole,
        user_background: userBackground,
      });
    }
    setSelectedMemory(null);
    router.push("/interview");
  };

  return (
    <div className="w-full max-w-[760px] mx-auto flex flex-col gap-7 relative py-3 md:py-6">
      
      {isLoading && (
        <div data-testid="coach-skeleton" className="animate-pulse space-y-4 py-6">
          <div className="h-6 w-48 rounded bg-[#e8e7e2]" />
          <div className="h-4 w-72 rounded bg-[#e8e7e2]" />
          <div className="h-4 w-56 rounded bg-[#e8e7e2]" />
        </div>
      )}

      {!isLoading && (
        <>
          {/* 1. Coach 身份条 */}
          <div className="flex items-center gap-3.5 pb-4.5 pr-[220px] max-[768px]:pr-0 border-b border-[#e8e7e2]">
            <div className="relative w-[52px] h-[52px] rounded-full shrink-0 bg-gradient-to-br from-[#7c3aed] to-[#4f46e5] text-white font-[var(--mac-font-display)] text-[22px] flex items-center justify-center shadow-[0_0_0_4px_rgba(124,58,237,0.08),0_6px_18px_rgba(124,58,237,0.18)] select-none">
              C
              <span
                className={`absolute right-[-1px] bottom-[-1px] w-3 h-3 rounded-full border-2 border-white transition-colors duration-300 ${
                  userState === "returning" ? "bg-[#059669]" : "bg-[#7c3aed]"
                }`}
              />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-[var(--mac-font-display)] text-xl text-[#171717] leading-tight">Coach</div>
              {userState === "returning" ? (
                <div className="text-xs text-[#8a8a8a] mt-1 flex gap-2 items-center">
                  <span>你的 AI 面试教练</span>
                  <span className="w-0.75 h-0.75 rounded-full bg-[#8a8a8a]" />
                  <span>已陪你 <b className="text-[#525252] font-semibold">{contextData?.session_count ?? 0} 场</b></span>
                </div>
              ) : (
                <div className="text-xs text-[#8a8a8a] mt-1 flex gap-2 items-center">
                  <span>你的 AI 面试教练</span>
                  <span className="w-0.75 h-0.75 rounded-full bg-[#8a8a8a]" />
                  <span>我们第一次见面</span>
                </div>
              )}
            </div>
          </div>

          {/* 2. 用户消息气泡（每轮覆盖显示最新一条） */}
          {userMessage && (
            <div className="flex justify-end px-1 animate-in fade-in slide-in-from-bottom-2 duration-300">
              <div>
                <div className="max-w-[78%] ml-auto px-3.5 py-2.5 bg-white border border-[#e8e7e2] rounded-[14px_14px_4px_14px] text-[#171717] text-[13px] leading-[1.55] shadow-xs">
                  {userMessage}
                </div>
                <div className="text-[10px] text-[#8a8a8a] mt-1 text-right pr-1">
                  刚刚 · 你
                </div>
              </div>
            </div>
          )}

          {/* 3. Coach 呼吸状态 */}
          {isThinking && (
            <div className="flex gap-4 px-1 animate-in fade-in duration-200">
              <div className="w-[2px] shrink-0 rounded-[2px] bg-[#7c3aed] opacity-30" />
              <div className="flex items-center gap-2.5 text-[#8a8a8a] text-[13px] font-sans">
                <div className="w-2 h-2 rounded-full bg-[#7c3aed] animate-coach-pulse" />
              </div>
            </div>
          )}

          {/* 4. Coach 说话文字区 */}
          {!isThinking && (
            <div className="flex gap-4 px-1 animate-in fade-in duration-300">
              <div className="w-[2px] shrink-0 rounded-[2px] bg-gradient-to-b from-[#7c3aed] to-[#4f46e5] opacity-50" />
              <div className="flex-1 font-[var(--mac-font-display)] text-xl md:text-[22px] leading-[1.55] text-[#171717] font-normal">
                
                {/* 4.1 初始阶段（开场两态） */}
                {speechStage === "initial" && (
                  <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
                    <CoachOpeningCopy
                      coachMessage={coachMessage}
                      fallbackUserState={userState}
                      fallbackSessionCount={contextData?.session_count ?? 0}
                    />
                  </div>
                )}

                {/* 4.2 点击“好，今天就练这个”后的“开始面试”卡片渲染 */}
                {speechStage === "follow" && (
                  <div className="animate-in fade-in slide-in-from-bottom-3 duration-500">
                    <Card className="my-3.5 p-3.5 px-4 border border-[#7c3aed]/20 rounded-2xl bg-gradient-to-br from-[#f5f3ff] to-[#7c3aed]/[0.04] shadow-[0_4px_14px_rgba(124,58,237,0.08)] ring-0 font-sans gap-0">
                      <div className="text-[10px] font-extrabold tracking-[0.12em] uppercase text-[#7c3aed] mb-1.5 select-none">即将进入</div>
                      <div className="font-[var(--mac-font-display)] text-lg text-[#171717] leading-tight mb-1">第 #{(contextData?.session_count ?? 0) + 1} 场 · 多 Agent 委员会</div>
                      <div className="text-xs text-[#8a8a8a] flex gap-2.5 flex-wrap mt-1">
                        <span>本场重点 <b className="text-[#525252] font-semibold">量化结果 · 失败降级</b></span>
                        <span>预计 <b className="text-[#525252] font-semibold">30 min</b></span>
                      </div>
                      
                      <div className="mt-3.5 border-t border-[#7c3aed]/10 pt-3">
                        <button
                          type="button"
                          onClick={() => setShowJdInput(!showJdInput)}
                          className="flex items-center gap-1.5 text-xs text-[#7c3aed] font-semibold hover:text-[#4f46e5] active:scale-95 transition-all select-none"
                        >
                          <span>{showJdInput ? "▲ 收起" : "▼ 我有 JD · 深度定制考点 (可选)"}</span>
                        </button>
                        {showJdInput && (
                          <div className="mt-2.5 space-y-2 animate-in slide-in-from-top-1 duration-200">
                            <Textarea
                              value={jdText}
                              onChange={(e) => setJdText(e.target.value)}
                              placeholder="粘贴目标职位的 JD 文本，或输入招聘要求..."
                              className="text-xs bg-white/70 border-[#7c3aed]/20 focus-visible:ring-[#7c3aed]/30 min-h-[72px]"
                            />
                            <div className="flex gap-2">
                              <input
                                type="text"
                                value={jdUrl}
                                onChange={(e) => setJdUrl(e.target.value)}
                                placeholder="或粘贴 JD 的网址链接 (可选)..."
                                className="flex-1 text-[11px] px-3 py-1.5 rounded-lg border border-[#7c3aed]/20 bg-white/70 outline-none focus:border-[#7c3aed] text-[#171717]"
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    </Card>
                  </div>
                )}

                {/* 4.3 点击“等等，我想换方向” */}
                {speechStage === "switch" && (
                  <div className="animate-in fade-in slide-in-from-bottom-3 duration-500">
                    <p>好。那你今天想换的是 ——</p>
                  </div>
                )}

                {/* 4.4 选了要换什么（岗位/技术栈/项目） */}
                {speechStage === "switch-target" && (
                  <div className="animate-in fade-in slide-in-from-bottom-3 duration-500">
                    <p>明白。正在为你打开设置页。</p>
                  </div>
                )}

                {/* 4.5 新用户点选了岗位 */}
                {speechStage === "new-role" && (
                  <div className="animate-in fade-in slide-in-from-bottom-3 duration-500">
                    <p>好。<span className="text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans">{selectedRole}</span>。</p>
                    <p className="mt-3.5">
                      那再给我一分钟 —— 用一两句话告诉我，<br />
                      你最想拿出来讲的<span className="text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans">那个项目</span>，是什么？
                    </p>
                  </div>
                )}

                {/* 4.6 底部发送消息后 */}
                {speechStage === "custom-reply" && (
                  <div className="animate-in fade-in slide-in-from-bottom-3 duration-500">
                    <p>听到了。</p>
                    <p className="mt-3.5">我先把这条记下来，<span className="text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans">下一场会带着这个上下文</span>开始。</p>
                    <p className="mt-3.5">你现在想要 ——</p>
                  </div>
                )}

              </div>
            </div>
          )}

          {/* 5. 行动 CTA 区域（根据状态机做对应渲染） */}
          {!isThinking && (
            <div className="flex gap-2.5 flex-wrap pl-[18px] mt-1 animate-in fade-in duration-300">
              
              {/* 5.1 初始阶段（老用户） */}
              {userState === "returning" && speechStage === "initial" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAction("follow")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-transparent transition-all bg-[#171717] text-white shadow-[0_6px_18px_rgba(23,23,23,0.18)] hover:bg-black hover:translate-y-[-1px]"
                  >
                    好，今天就练这个
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("switch")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-[#dcdbd5] transition-all bg-white text-[#525252] hover:border-[#b8b5aa] hover:text-[#171717]"
                  >
                    等等，我想换方向
                  </button>
                </>
              )}

              {/* 5.2 初始阶段（新用户） */}
              {userState === "new" && speechStage === "initial" && (
                <>
                  {["AI Agent 工程师", "前端工程师", "后端工程师", "Python 工程师", "全栈工程师"].map((role) => (
                    <button
                      key={role}
                      type="button"
                      onClick={() => handleAction("new-role", role)}
                      className={`px-3.5 py-2 rounded-full border text-xs font-sans cursor-pointer transition-all hover:border-[#171717] hover:text-[#171717] hover:translate-y-[-1px] ${
                        role === "AI Agent 工程师"
                          ? "bg-[#171717] text-white border-[#171717] font-semibold hover:bg-black"
                          : "bg-white border-[#dcdbd5] text-[#525252]"
                      }`}
                    >
                      {role}
                    </button>
                  ))}
                </>
              )}

              {/* 5.3 开始面试确认页 (follow) */}
              {speechStage === "follow" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAction("go-room")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-transparent transition-all bg-[#171717] text-white shadow-[0_6px_18px_rgba(23,23,23,0.18)] hover:bg-black hover:translate-y-[-1px]"
                  >
                    开始面试
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("reset")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-[#dcdbd5] transition-all bg-white text-[#525252] hover:border-[#b8b5aa] hover:text-[#171717]"
                  >
                    算了，再聊聊
                  </button>
                </>
              )}

              {/* 5.4 换方向选项页 (switch) */}
              {speechStage === "switch" && (
                <>
                  {[
                    { key: "role", label: "换个目标岗位" },
                    { key: "stack", label: "换个技术栈" },
                    { key: "project", label: "换个项目讲" },
                  ].map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => handleAction("switch-target", item.label)}
                      className="px-3.5 py-2 rounded-full bg-white border border-[#dcdbd5] text-[#525252] text-xs font-sans cursor-pointer transition-all hover:border-[#171717] hover:text-[#171717] hover:translate-y-[-1px]"
                    >
                      {item.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => handleAction("reset")}
                    className="px-3.5 py-2 rounded-full bg-white border border-[#dcdbd5] text-[#525252] text-xs font-sans cursor-pointer transition-all hover:border-[#171717] hover:text-[#171717] hover:translate-y-[-1px]"
                  >
                    我想想，先回到刚才
                  </button>
                </>
              )}

              {/* 5.5 跳转至配置确认页 (switch-target) */}
              {speechStage === "switch-target" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAction("go-setup")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-transparent transition-all bg-[#171717] text-white shadow-[0_6px_18px_rgba(23,23,23,0.18)] hover:bg-black hover:translate-y-[-1px]"
                  >
                    打开
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("reset")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-[#dcdbd5] transition-all bg-white text-[#525252] hover:border-[#b8b5aa] hover:text-[#171717]"
                  >
                    不了
                  </button>
                </>
              )}

              {/* 5.6 新用户选择岗位后的确认 */}
              {speechStage === "new-role" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAction("go-room")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-transparent transition-all bg-[#171717] text-white shadow-[0_6px_18px_rgba(23,23,23,0.18)] hover:bg-black hover:translate-y-[-1px]"
                  >
                    我直接试一场吧
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("reset")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-[#dcdbd5] transition-all bg-white text-[#525252] hover:border-[#b8b5aa] hover:text-[#171717]"
                  >
                    让我想想
                  </button>
                </>
              )}

              {/* 5.7 底部发送消息后 */}
              {speechStage === "custom-reply" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAction("go-room")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-transparent transition-all bg-[#171717] text-white shadow-[0_6px_18px_rgba(23,23,23,0.18)] hover:bg-black hover:translate-y-[-1px]"
                  >
                    直接进考场
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("go-setup")}
                    className="px-3.5 py-2 rounded-full bg-white border border-[#dcdbd5] text-[#525252] text-xs font-sans cursor-pointer transition-all hover:border-[#171717] hover:text-[#171717] hover:translate-y-[-1px]"
                  >
                    先调一下配置
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("reset")}
                    className="px-3.5 py-2 rounded-full bg-white border border-[#dcdbd5] text-[#525252] text-xs font-sans cursor-pointer transition-all hover:border-[#171717] hover:text-[#171717] hover:translate-y-[-1px]"
                  >
                    再聊聊
                  </button>
                </>
              )}

            </div>
          )}

          {/* 6. 历史面试记忆（仅在老用户态下展示） */}
          {userState === "returning" && (
            <div className="mt-2.5 border-t border-[#e8e7e2] pt-5.5 animate-in fade-in duration-300">
              <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <div className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#8a8a8a] select-none">
                    近期记忆
                  </div>
                  <div className="mt-1 text-xs text-[#8a8a8a]">
                    Coach 只露出最值得接着练的几场，完整历史放在个人仪表盘
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className="rounded-full bg-[#faf9f5] px-2.5 py-1 text-[11px] font-semibold text-[#8a8a8a]">
                    显示 {previewMemorySessions.length} / {memorySessions.length}
                  </span>
                  <Link
                    href="/dashboard"
                    className="rounded-full border border-[#dcdbd5] bg-white px-3 py-1.5 text-xs font-semibold text-[#525252] transition-all hover:border-[#b8b5aa] hover:text-[#171717]"
                  >
                    查看全部记忆
                  </Link>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {previewMemorySessions.map((session) => (
                  <MemorySessionCard
                    key={session.id}
                    session={session}
                    onClick={() => setSelectedMemory(session)}
                  />
                ))}
              </div>
            </div>
          )}

          <MemorySessionModal
            session={selectedMemory}
            onClose={() => setSelectedMemory(null)}
            onPracticeAgain={(session) => {
              void handlePracticeMemory(session);
            }}
          />

          {/* 7. 底部回应输入框区域 */}
          <div className="mt-1.5">
            <div className="p-3 bg-white border border-[#e8e7e2] rounded-[14px] shadow-sm flex items-end gap-2.5">
              <textarea
                ref={textareaRef}
                rows={1}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="或者直接告诉我你想聊什么..."
                className="flex-1 border-0 outline-none resize-none bg-transparent text-[#171717] text-sm leading-relaxed p-1.5 py-1 min-h-[28px] max-h-[96px] focus-visible:ring-0 focus-visible:ring-offset-0 focus:outline-none focus:ring-0 custom-textarea-scrollbar font-sans"
              />
              <button
                type="button"
                onClick={handleSend}
                className="w-[38px] h-[38px] rounded-[10px] bg-[#171717] text-white flex items-center justify-center transition-all cursor-pointer hover:bg-black hover:translate-y-[-1px] select-none text-[18px]"
              >
                ↑
              </button>
            </div>
            <div className="pl-1 text-[11px] text-[#8a8a8a] mt-1.5 select-none">
              按 Enter 发送 · Shift + Enter 换行
            </div>
          </div>
        </>
      )}

    </div>
  );
}
