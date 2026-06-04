"use client";

import type { ReactIteration, TraceNodeStatus } from "@/lib/prepare-types";
import { ReactToolTree } from "./react-tool-tree";

export type { TraceNodeStatus };

interface TraceNodeProps {
  id: string;
  label: string;
  title: string;
  status: TraceNodeStatus;
  tokens: string;
  elapsedMs?: number;
  isLast?: boolean;
  candidateLevel?: "beginner" | "junior" | "mid" | "senior";
  latentSignals?: string[];
  missingDimensions?: string[];
  followupFocus?: string;
  chiefToolCalls?: string[];
  designedQuestion?: string;
  designedCategory?: string;
  designedSource?: string;
  summaryScore?: number;
  reactSteps?: ReactIteration[];
  reactStatus?: "running" | "done";
  weakAreas?: string[];
  recordCount?: number;
  reactIterations?: number;
  reactToolCount?: number;
  companyName?: string;
  gaps?: string[];
  jdCompany?: string;
  jdRole?: string;
  jdDifficulty?: string;
  jdKeySkills?: string[];
  questionStats?: Record<string, number>;
  questionTotal?: number;
}

export function TraceNode(props: TraceNodeProps) {
  const {
    id,
    label,
    title,
    status,
    elapsedMs,
    isLast = false,
  } = props;
  const badgeClass = getBadgeClass(id);

  return (
    <div data-testid={`trace-node-${id}`} className="group flex gap-3 py-2.5">
      <div className="relative flex flex-col items-center pt-0.5 w-5 flex-shrink-0 self-stretch">
        {!isLast && (
          <div className="absolute top-7 bottom-[-10px] w-[2px] bg-gradient-to-b from-[#534AB7]/60 via-[#534AB7]/25 to-transparent dark:from-[#CECBF6]/45 dark:via-[#CECBF6]/15 dark:to-transparent" />
        )}
        <div
          data-testid={`trace-status-${status}`}
          className={`relative z-10 flex h-5 w-5 items-center justify-center rounded-full border-[1.5px] transition-all duration-500 shadow-sm ${
            status === "running"
              ? "animate-pulse border-[#534AB7] bg-white text-[#534AB7] ring-4 ring-[#534AB7]/20 dark:border-[#CECBF6] dark:bg-zinc-950 shadow-[0_0_12px_rgba(83,74,183,0.35)] dark:shadow-[0_0_12px_rgba(206,203,246,0.3)]"
              : status === "done"
                ? "border-emerald-500 bg-emerald-50 text-emerald-600 dark:border-emerald-500/70 dark:bg-emerald-500/20 dark:text-emerald-400"
                : "border-[#534AB7]/45 bg-white text-[#534AB7]/60 dark:border-white/30 dark:bg-zinc-950"
          }`}
        >
          {status === "done" ? (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="3.5"
              className="h-2.5 w-2.5"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <div
              className={`h-1.5 w-1.5 rounded-full ${
                status === "running"
                  ? "bg-[#534AB7] dark:bg-[#CECBF6]"
                  : "bg-[#534AB7]/50 dark:bg-white/30"
              }`}
            />
          )}
        </div>
      </div>

      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <span
              className={`flex-shrink-0 rounded px-1.5 py-0.5 text-[10px] font-extrabold tracking-wide uppercase transition-all duration-300 shadow-sm ${badgeClass}`}
            >
              {label}
            </span>
            <span className="text-xs font-bold tracking-tight text-slate-900 dark:text-slate-100 truncate">
              {title}
            </span>
          </div>
          {elapsedMs !== undefined && elapsedMs > 0 && (
            <span className="flex-shrink-0 text-[11px] tabular-nums font-semibold text-slate-500 dark:text-zinc-400">
              {elapsedMs}ms
            </span>
          )}
        </div>
        {renderContent(id, props)}
      </div>
    </div>
  );
}

function renderContent(id: string, props: TraceNodeProps) {
  switch (id) {
    case "memory_search":
      return <MemoryContent {...props} />;
    case "research_agent":
      return <ResearchContent {...props} />;
    case "jd_analysis":
      return <JdContent {...props} />;
    case "question_gen":
      return <QuestionContent {...props} />;
    case "evaluator":
      return <EvaluatorContent {...props} />;
    case "chief_think":
      return <ChiefThinkContent {...props} />;
    case "followup":
    case "ask_question":
      return <FollowupContent {...props} />;
    default:
      return <TokenContent {...props} />;
  }
}

function MemoryContent(props: TraceNodeProps) {
  if (props.status === "running") {
    return <div className="ml-1"><p className="text-[11px] opacity-75 animate-pulse font-medium">正在读取历史表现...</p></div>;
  }
  return (
    <div className="ml-1">
      <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">
        {props.weakAreas && props.weakAreas.length > 0 ? (
          <>
            读取到 {props.recordCount ?? 0} 条记录，薄弱点：
            <span className="text-red-600 font-semibold">{props.weakAreas.join("、")}</span>
          </>
        ) : (
          "暂无历史薄弱点记录"
        )}
      </p>
    </div>
  );
}

function ResearchContent(props: TraceNodeProps) {
  return (
    <div className="ml-1 space-y-2">
      {props.status === "done" && (
        <div className="flex flex-wrap gap-1.5 mb-2.5 animate-in fade-in slide-in-from-top-1 duration-500">
          <span className="text-[9px] bg-slate-100 text-slate-700/85 border border-slate-200/60 rounded px-1.5 py-0.5 font-extrabold dark:bg-slate-800/60 dark:text-slate-300 dark:border-zinc-700/40">
            {props.reactIterations ?? 0} 轮 · {props.reactToolCount ?? 0} 次工具调用
          </span>
          {props.companyName && (
            <span className="text-[9px] bg-blue-50 text-blue-700/85 border border-blue-200/60 rounded px-1.5 py-0.5 font-extrabold dark:bg-blue-900/20 dark:text-blue-300 dark:border-blue-700/40">
              {props.companyName}
            </span>
          )}
          {props.gaps && props.gaps.length > 0 && (
            <span className="text-[9px] bg-rose-50 text-rose-700/85 border border-rose-200/60 rounded px-1.5 py-0.5 font-extrabold dark:bg-rose-900/20 dark:text-rose-300 dark:border-rose-700/40">
              Gap：{props.gaps.join(" · ")}
            </span>
          )}
        </div>
      )}
      {props.reactSteps && props.reactSteps.length > 0 && (
        <ReactToolTree steps={props.reactSteps} isFinished={props.status === "done"} />
      )}
    </div>
  );
}

function JdContent(props: TraceNodeProps) {
  if (props.status === "running") {
    return <div className="ml-1"><p className="text-[11px] opacity-75 animate-pulse font-medium">正在分析岗位需求...</p></div>;
  }
  return (
    <div className="ml-1">
      <p className="text-[11px] font-semibold text-slate-800 dark:text-slate-200">
        {props.jdCompany || "未知公司"} · {props.jdRole || "未知岗位"} · 难度 {props.jdDifficulty || "未知"}
      </p>
      {props.jdKeySkills && props.jdKeySkills.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-1.5">
          {props.jdKeySkills.map(skill => (
            <span key={skill} className="text-[9px] bg-amber-50 text-amber-700/85 border border-amber-200/60 rounded px-1.5 py-0.5 font-bold dark:bg-amber-900/20 dark:text-amber-300 dark:border-amber-700/40">
              {skill}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function QuestionContent(props: TraceNodeProps) {
  if (props.status === "running") {
    return <div className="ml-1"><p className="text-[11px] opacity-75 animate-pulse font-medium">正在为你定制专属题目...</p></div>;
  }
  
  const statsTexts = [];
  if (props.questionStats?.technical) statsTexts.push(`技术 ×${props.questionStats.technical}`);
  if (props.questionStats?.behavioral) statsTexts.push(`行为 ×${props.questionStats.behavioral}`);
  if (props.questionStats?.system_design) statsTexts.push(`系统设计 ×${props.questionStats.system_design}`);

  return (
    <div className="ml-1">
      <p className="text-xs text-slate-600 font-medium">
        已定制 {props.questionTotal ?? 0} 道，面试中逐题呈现
        {statsTexts.length > 0 && ` · ${statsTexts.join(" · ")}`}
      </p>
    </div>
  );
}

function EvaluatorContent(props: TraceNodeProps) {
  return (
    <div className="ml-1">
      {props.status === "done" && (
        <div className="flex flex-wrap gap-1.5 mb-2.5 animate-in fade-in slide-in-from-top-1 duration-500">
          {typeof props.summaryScore === "number" && (
            <span className="text-[9px] bg-violet-100 text-violet-700/85 border border-violet-200/60 rounded px-1.5 py-0.5 font-extrabold dark:bg-violet-950/20 dark:text-violet-300 dark:border-[#CECBF6]/25">
              评分：{props.summaryScore.toFixed(1)} / 10
            </span>
          )}
          {props.candidateLevel && (
            <span className="text-[9px] bg-[#534AB7]/10 text-[#534AB7]/85 border border-[#534AB7]/20 rounded px-1.5 py-0.5 font-bold uppercase tracking-wider dark:bg-white/8 dark:text-white/65 dark:border-white/20">
              {props.candidateLevel === "beginner"
                ? "初学者"
                : props.candidateLevel === "junior"
                  ? "初级"
                  : props.candidateLevel === "mid"
                    ? "中级"
                    : "高级"}
            </span>
          )}
          {props.latentSignals &&
            props.latentSignals.slice(0, 3).map((signal) => (
              <span
                key={signal}
                className="text-[9px] bg-emerald-50 text-emerald-700/85 border border-emerald-200/60 rounded px-1.5 py-0.5 font-bold dark:bg-emerald-500/10 dark:text-emerald-400/85 dark:border-emerald-500/25"
              >
                {signal}
              </span>
            ))}
          {props.missingDimensions && props.missingDimensions.length > 0 && (
            <span className="text-[9px] text-rose-600/85 border border-rose-200/60 bg-rose-50/60 rounded px-1.5 py-0.5 font-bold dark:text-rose-400/85 dark:border-rose-500/25 dark:bg-rose-500/8">
              缺失：{props.missingDimensions.join(" · ")}
            </span>
          )}
        </div>
      )}
      <TokenContent {...props} />
    </div>
  );
}

function ChiefThinkContent(props: TraceNodeProps) {
  return (
    <div className="ml-1">
      {props.status === "done" && props.chiefToolCalls && props.chiefToolCalls.length > 0 && (
        <div className="mb-2.5 flex flex-wrap gap-1.5 pl-2.5 border-l-[1.5px] border-[#534AB7]/20 dark:border-white/15 animate-in fade-in slide-in-from-top-1 duration-500">
          {props.chiefToolCalls.map((tool) => (
            <span
              key={tool}
              className="rounded bg-sky-50 text-sky-700 border border-sky-200/70 px-1.5 py-0.5 text-[9px] font-extrabold dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-700/40"
            >
              {formatChiefToolName(tool)}
            </span>
          ))}
        </div>
      )}
      {props.status === "done" && (
        <div className="flex flex-wrap gap-1.5 mb-2.5 animate-in fade-in slide-in-from-top-1 duration-500">
          {typeof props.summaryScore === "number" && (
            <span className="text-[9px] bg-violet-100 text-violet-700/85 border border-violet-200/60 rounded px-1.5 py-0.5 font-extrabold dark:bg-violet-950/20 dark:text-violet-300 dark:border-[#CECBF6]/25">
              评分：{props.summaryScore.toFixed(1)} / 10
            </span>
          )}
          {props.candidateLevel && (
            <span className="text-[9px] bg-[#534AB7]/10 text-[#534AB7]/85 border border-[#534AB7]/20 rounded px-1.5 py-0.5 font-bold uppercase tracking-wider dark:bg-white/8 dark:text-white/65 dark:border-white/20">
              {props.candidateLevel === "beginner"
                ? "初学者"
                : props.candidateLevel === "junior"
                  ? "初级"
                  : props.candidateLevel === "mid"
                    ? "中级"
                    : "高级"}
            </span>
          )}
          {props.latentSignals &&
            props.latentSignals.slice(0, 3).map((signal) => (
              <span
                key={signal}
                className="text-[9px] bg-emerald-50 text-emerald-700/85 border border-emerald-200/60 rounded px-1.5 py-0.5 font-bold dark:bg-emerald-500/10 dark:text-emerald-400/85 dark:border-emerald-500/25"
              >
                {signal}
              </span>
            ))}
          {props.missingDimensions && props.missingDimensions.length > 0 && (
            <span className="text-[9px] text-rose-600/85 border border-rose-200/60 bg-rose-50/60 rounded px-1.5 py-0.5 font-bold dark:text-rose-400/85 dark:border-rose-500/25 dark:bg-rose-500/8">
              缺失：{props.missingDimensions.join(" · ")}
            </span>
          )}
        </div>
      )}
      <TokenContent {...props} />
    </div>
  );
}

function FollowupContent(props: TraceNodeProps) {
  const focus = props.missingDimensions && props.missingDimensions.length > 0
    ? props.missingDimensions.join(" · ")
    : props.followupFocus;
    
  return (
    <div className="ml-1 space-y-2">
      {props.status === "done" && focus && (
        <div className="flex gap-2 items-start animate-in fade-in slide-in-from-top-1 duration-500">
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
            追问方向：{focus}
          </span>
        </div>
      )}
      <TokenContent {...props} />
    </div>
  );
}

function TokenContent(props: TraceNodeProps) {
  if (!props.tokens) return null;
  return (
    <div className={`space-y-1.5 whitespace-pre-wrap p-3 rounded-xl border text-xs font-medium leading-relaxed animate-in fade-in slide-in-from-top-1 duration-500 ${getChainCardClass(props.id)}`}>
      {props.tokens.split("\n").map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) return null;
        if (
          trimmed.startsWith("[") ||
          trimmed.startsWith("{") ||
          trimmed.includes('": "')
        )
          return null;
        return (
          <div
            key={i}
            className="flex gap-2 items-start mt-1.5 animate-in fade-in slide-in-from-left-2 duration-300"
          >
            <span className={`flex-shrink-0 select-none mt-[3px] font-mono text-[8px] font-bold ${getArrowColor(props.id)}`}>
              →
            </span>
            <span className="break-words">
              {trimmed.replace(/^[•\-]\s*/, "")}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function formatChiefToolName(tool: string) {
  if (tool === "evaluate_answer") return "评估回答";
  if (tool === "design_question") return "设计新题";
  if (tool === "query_profile") return "读取画像";
  return tool;
}

function getBadgeClass(id: string) {
  if (id === "master" || id === "chief_think") {
    return "border border-violet-200 bg-gradient-to-r from-violet-100 to-indigo-100 text-indigo-700 dark:border-indigo-700/60 dark:from-indigo-900/50 dark:to-violet-900/50 dark:text-indigo-300";
  }
  if (
    id === "question_gen" ||
    id === "ask_question" ||
    id === "chief_respond"
  ) {
    return "border border-blue-200 bg-gradient-to-r from-blue-100 to-sky-100 text-blue-700 dark:border-blue-700/60 dark:from-blue-900/50 dark:to-sky-900/50 dark:text-blue-300";
  }
  if (id === "evaluator") {
    return "border border-emerald-200 bg-gradient-to-r from-emerald-100 to-teal-100 text-teal-700 dark:border-teal-700/60 dark:from-teal-900/50 dark:to-emerald-900/50 dark:text-teal-300";
  }
  if (id === "followup") {
    return "border border-pink-200 bg-gradient-to-r from-pink-100 to-rose-100 text-pink-700 dark:border-pink-700/60 dark:from-pink-900/50 dark:to-rose-900/50 dark:text-pink-300";
  }
  if (id === "memory_search") {
    return "border border-cyan-200 bg-gradient-to-r from-cyan-100 to-emerald-100 text-cyan-700 dark:border-cyan-700/60 dark:from-cyan-900/50 dark:to-emerald-900/50 dark:text-cyan-300";
  }
  if (id === "jd_analysis") {
    return "border border-amber-200 bg-gradient-to-r from-amber-100 to-orange-100 text-amber-700 dark:border-amber-700/60 dark:from-amber-900/50 dark:to-orange-900/50 dark:text-amber-300";
  }
  if (id === "closing") {
    return "border border-slate-300 bg-slate-100 text-slate-600 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-400";
  }
  return "border border-slate-200 bg-slate-100/80 text-slate-600 dark:border-zinc-700 dark:bg-zinc-800/40 dark:text-zinc-400";
}

function getChainCardClass(id: string) {
  if (id === "master" || id === "chief_think") {
    return "bg-gradient-to-r from-violet-500/10 to-indigo-500/5 border-violet-200/70 text-violet-950 dark:from-violet-950/20 dark:to-indigo-950/10 dark:border-violet-800/40 dark:text-violet-200 shadow-sm";
  }
  if (
    id === "question_gen" ||
    id === "ask_question" ||
    id === "chief_respond"
  ) {
    return "bg-gradient-to-r from-sky-500/10 to-blue-500/5 border-sky-200/70 text-sky-950 dark:from-sky-950/20 dark:to-blue-950/10 dark:border-sky-800/40 dark:text-sky-200 shadow-sm";
  }
  if (id === "evaluator") {
    return "bg-gradient-to-r from-emerald-500/10 to-teal-500/5 border-emerald-250/70 text-emerald-950 dark:from-emerald-950/20 dark:to-teal-950/10 dark:border-emerald-800/40 dark:text-emerald-200 shadow-sm";
  }
  if (id === "followup") {
    return "bg-gradient-to-r from-pink-500/10 to-rose-500/5 border-pink-200/70 text-pink-950 dark:from-pink-950/20 dark:to-rose-950/10 dark:border-pink-800/40 dark:text-pink-200 shadow-sm";
  }
  if (id === "memory_search") {
    return "bg-gradient-to-r from-cyan-500/10 to-emerald-500/5 border-cyan-200/70 text-cyan-950 dark:from-cyan-950/20 dark:to-emerald-950/10 dark:border-cyan-800/40 dark:text-cyan-200 shadow-sm";
  }
  if (id === "jd_analysis") {
    return "bg-gradient-to-r from-amber-500/10 to-orange-500/5 border-amber-250/70 text-amber-950 dark:from-amber-950/20 dark:to-orange-950/10 dark:border-amber-800/40 dark:text-amber-200 shadow-sm";
  }
  if (id === "closing") {
    return "bg-gradient-to-r from-slate-500/10 to-zinc-500/5 border-slate-300 text-slate-800 dark:from-zinc-800/20 dark:to-slate-800/10 dark:border-zinc-700/60 dark:text-zinc-300 shadow-sm";
  }
  return "bg-gradient-to-r from-slate-500/10 to-zinc-500/5 border-slate-200/70 text-slate-800 dark:from-zinc-800/20 dark:to-slate-800/10 dark:border-zinc-700/60 dark:text-zinc-300 shadow-sm";
}

function getArrowColor(id: string) {
  if (id === "master" || id === "chief_think") return "text-violet-500/80 dark:text-indigo-400/80";
  if (
    id === "question_gen" ||
    id === "ask_question" ||
    id === "chief_respond"
  ) {
    return "text-blue-500/80 dark:text-sky-400/80";
  }
  if (id === "evaluator") return "text-teal-500/80 dark:text-emerald-400/80";
  if (id === "followup") return "text-pink-500/80 dark:text-rose-400/80";
  if (id === "memory_search") return "text-cyan-500/80 dark:text-cyan-400/80";
  if (id === "jd_analysis") return "text-amber-500/80 dark:text-orange-400/80";
  return "text-slate-400 dark:text-zinc-500";
}