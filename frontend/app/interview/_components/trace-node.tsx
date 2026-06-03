"use client";

import type { TraceNodeStatus } from "@/lib/prepare-types";

export type { TraceNodeStatus };

interface TraceNodeProps {
  id: string;
  label: string;
  title: string;
  status: TraceNodeStatus;
  tokens: string; // 流式积累的文本（LLM 逐字输出，非固定文案）
  elapsedMs?: number;
  isLast?: boolean; // 标识是否为最后一个节点，用于完美裁断尾部悬空竖线
  candidateLevel?: "beginner" | "junior" | "mid" | "senior";
  latentSignals?: string[];
  missingDimensions?: string[];
  chiefToolCalls?: string[];
  designedQuestion?: string;
  designedCategory?: string;
  designedSource?: string;
  summaryScore?: number;
}

export function TraceNode({
  id,
  label,
  title,
  status,
  tokens,
  elapsedMs,
  isLast = false,
  candidateLevel,
  latentSignals,
  missingDimensions,
  chiefToolCalls,
  designedQuestion,
  designedCategory,
  summaryScore,
}: TraceNodeProps) {
  const badgeClass = getBadgeClass(id);

  return (
    <div data-testid={`trace-node-${id}`} className="group flex gap-3 py-2.5">
      <div className="relative flex flex-col items-center pt-0.5 w-5 flex-shrink-0 self-stretch">
        {/* 垂直 Timeline 连接线 */}
        {!isLast && (
          <div className="absolute top-7 bottom-[-10px] w-[2px] bg-gradient-to-b from-[#534AB7]/60 via-[#534AB7]/25 to-transparent dark:from-[#CECBF6]/45 dark:via-[#CECBF6]/15 dark:to-transparent" />
        )}
        {/* 节点状态 Icon/Dot */}
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

        {/* 评估结果徽章：仅在 evaluator 或 chief_think 节点完成时展示 */}
        {(id === "evaluator" || id === "chief_think") && status === "done" && (
          <div className="flex flex-wrap gap-1.5 mb-2.5 animate-in fade-in slide-in-from-top-1 duration-500">
            {typeof summaryScore === "number" && (
              <span className="text-[9px] bg-violet-100 text-violet-700/85 border border-violet-200/60 rounded px-1.5 py-0.5 font-extrabold dark:bg-violet-950/20 dark:text-violet-300 dark:border-[#CECBF6]/25">
                评分：{summaryScore.toFixed(1)} / 10
              </span>
            )}
            {candidateLevel && (
              <span className="text-[9px] bg-[#534AB7]/10 text-[#534AB7]/85 border border-[#534AB7]/20 rounded px-1.5 py-0.5 font-bold uppercase tracking-wider dark:bg-white/8 dark:text-white/65 dark:border-white/20">
                {candidateLevel === "beginner"
                  ? "初学者"
                  : candidateLevel === "junior"
                    ? "初级"
                    : candidateLevel === "mid"
                      ? "中级"
                      : "高级"}
              </span>
            )}
            {latentSignals &&
              latentSignals.slice(0, 3).map((signal) => (
                <span
                  key={signal}
                  className="text-[9px] bg-emerald-50 text-emerald-700/85 border border-emerald-200/60 rounded px-1.5 py-0.5 font-bold dark:bg-emerald-500/10 dark:text-emerald-400/85 dark:border-emerald-500/25"
                >
                  {signal}
                </span>
              ))}
            {missingDimensions && missingDimensions.length > 0 && (
              <span className="text-[9px] text-rose-600/85 border border-rose-200/60 bg-rose-50/60 rounded px-1.5 py-0.5 font-bold dark:text-rose-400/85 dark:border-rose-500/25 dark:bg-rose-500/8">
                缺失：{missingDimensions.join(" · ")}
              </span>
            )}
          </div>
        )}

        {id === "chief_think" &&
          status === "done" &&
          chiefToolCalls &&
          chiefToolCalls.length > 0 && (
            <div className="mb-2.5 flex flex-wrap gap-1.5 pl-2.5 border-l-[1.5px] border-[#534AB7]/20 dark:border-white/15 animate-in fade-in slide-in-from-top-1 duration-500">
              {chiefToolCalls.map((tool) => (
                <span
                  key={tool}
                  className="rounded bg-sky-50 text-sky-700 border border-sky-200/70 px-1.5 py-0.5 text-[9px] font-extrabold dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-700/40"
                >
                  {formatChiefToolName(tool)}
                </span>
              ))}
            </div>
          )}

        {/* 出题信息展示：chief_think / chief_respond 节点显示 designer 输出的题目 */}
        {(id === "chief_think" || id === "chief_respond") &&
          status === "done" &&
          designedQuestion && (
            <div className="mb-3 ml-1 animate-in fade-in slide-in-from-top-1 duration-500">
              <div className="flex gap-2 items-start p-3 rounded-xl bg-gradient-to-r from-sky-500/10 to-blue-500/5 border border-sky-200/60 dark:from-sky-500/15 dark:to-blue-500/10 dark:border-sky-500/35 shadow-sm">
                <span className="flex-shrink-0 text-xs mt-[1px]">📝</span>
                <span className="text-xs leading-relaxed text-sky-950 dark:text-sky-200 font-bold">
                  下一题：{designedCategory ? `[${formatQuestionCategory(designedCategory)}] ` : ""}
                  {designedQuestion}
                </span>
              </div>
            </div>
          )}

        {/* 准备阶段出题节点：不渲染题目详情，仅显示完成提示 */}
        {id === "question_gen" && (
          <div className={`space-y-1.5 ml-1 p-3 rounded-xl border animate-in fade-in slide-in-from-top-1 duration-500 ${getChainCardClass(id)}`}>
            {status === "running" ? (
              <p className="text-[11px] opacity-75 animate-pulse font-medium">
                正在为你定制专属题目...
              </p>
            ) : (
              <p className="text-[11px] font-semibold">
                已为你定制 5 道专属面试题，面试中将逐题呈现。
              </p>
            )}
          </div>
        )}

        {/* 其他节点（如 Master）：展示流式思维链文本，过滤 JSON 特征 */}
        {id !== "question_gen" && tokens && (
          <div className={`space-y-1.5 whitespace-pre-wrap ml-1 p-3 rounded-xl border text-xs font-medium leading-relaxed animate-in fade-in slide-in-from-top-1 duration-500 ${getChainCardClass(id)}`}>
            {tokens.split("\n").map((line, i) => {
              const trimmed = line.trim();
              if (!trimmed) return null;
              // 彻底过滤掉可能误出的 JSON 标记
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
                  <span className={`flex-shrink-0 select-none mt-[3px] font-mono text-[8px] font-bold ${getArrowColor(id)}`}>
                    →
                  </span>
                  <span className="break-words">
                    {trimmed.replace(/^[•\-]\s*/, "")}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function formatChiefToolName(tool: string) {
  if (tool === "evaluate_answer") return "评估回答";
  if (tool === "design_question") return "设计题目";
  if (tool === "query_profile") return "读取画像";
  return tool;
}

function formatQuestionCategory(category: string) {
  if (category === "technical") return "技术";
  if (category === "behavioral") return "行为";
  if (category === "system_design") return "系统设计";
  return category;
}

function getBadgeClass(id: string) {
  // 1. 核心调度 (Master / chief_think) - 幽静紫，加深背景
  if (id === "master" || id === "chief_think") {
    return "border border-violet-200 bg-gradient-to-r from-violet-100 to-indigo-100 text-indigo-700 dark:border-indigo-700/60 dark:from-indigo-900/50 dark:to-violet-900/50 dark:text-indigo-300";
  }

  // 2. 出题专家 (Question Gen / Ask Question / chief_respond) - 天空蓝
  if (
    id === "question_gen" ||
    id === "ask_question" ||
    id === "chief_respond"
  ) {
    return "border border-blue-200 bg-gradient-to-r from-blue-100 to-sky-100 text-blue-700 dark:border-blue-700/60 dark:from-blue-900/50 dark:to-sky-900/50 dark:text-blue-300";
  }

  // 3. 评估专家 (Evaluator) - 薄荷绿
  if (id === "evaluator") {
    return "border border-emerald-200 bg-gradient-to-r from-emerald-100 to-teal-100 text-teal-700 dark:border-teal-700/60 dark:from-teal-900/50 dark:to-emerald-900/50 dark:text-teal-300";
  }

  // 4. 面试专家/追问 (Followup) - 蔷薇粉
  if (id === "followup") {
    return "border border-pink-200 bg-gradient-to-r from-pink-100 to-rose-100 text-pink-700 dark:border-pink-700/60 dark:from-pink-900/50 dark:to-rose-900/50 dark:text-pink-300";
  }

  // 5. 记忆检索 (Memory Search) - 翡翠绿
  if (id === "memory_search") {
    return "border border-cyan-200 bg-gradient-to-r from-cyan-100 to-emerald-100 text-cyan-700 dark:border-cyan-700/60 dark:from-cyan-900/50 dark:to-emerald-900/50 dark:text-cyan-300";
  }

  // 6. JD分析 (JD Analysis) - 琥珀橙
  if (id === "jd_analysis") {
    return "border border-amber-200 bg-gradient-to-r from-amber-100 to-orange-100 text-amber-700 dark:border-amber-700/60 dark:from-amber-900/50 dark:to-orange-900/50 dark:text-amber-300";
  }

  // 7. 流程收尾 (Closing) - 中性灰
  if (id === "closing") {
    return "border border-slate-300 bg-slate-100 text-slate-600 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-400";
  }

  // 兜底样式
  return "border border-slate-200 bg-slate-100/80 text-slate-600 dark:border-zinc-700 dark:bg-zinc-800/40 dark:text-zinc-400";
}

function getChainCardClass(id: string) {
  // 1. 核心调度 (Master / chief_think) - 幽静紫渐变
  if (id === "master" || id === "chief_think") {
    return "bg-gradient-to-r from-violet-500/10 to-indigo-500/5 border-violet-200/70 text-violet-950 dark:from-violet-950/20 dark:to-indigo-950/10 dark:border-violet-800/40 dark:text-violet-200 shadow-sm";
  }

  // 2. 出题专家 (Question Gen / Ask Question / chief_respond) - 天空蓝渐变
  if (
    id === "question_gen" ||
    id === "ask_question" ||
    id === "chief_respond"
  ) {
    return "bg-gradient-to-r from-sky-500/10 to-blue-500/5 border-sky-200/70 text-sky-950 dark:from-sky-950/20 dark:to-blue-950/10 dark:border-sky-800/40 dark:text-sky-200 shadow-sm";
  }

  // 3. 评估专家 (Evaluator) - 薄荷绿渐变
  if (id === "evaluator") {
    return "bg-gradient-to-r from-emerald-500/10 to-teal-500/5 border-emerald-250/70 text-emerald-950 dark:from-emerald-950/20 dark:to-teal-950/10 dark:border-emerald-800/40 dark:text-emerald-200 shadow-sm";
  }

  // 4. 面试专家/追问 (Followup) - 蔷薇粉渐变
  if (id === "followup") {
    return "bg-gradient-to-r from-pink-500/10 to-rose-500/5 border-pink-200/70 text-pink-950 dark:from-pink-950/20 dark:to-rose-950/10 dark:border-pink-800/40 dark:text-pink-200 shadow-sm";
  }

  // 5. 记忆检索 (Memory Search) - 翡翠绿/青色渐变
  if (id === "memory_search") {
    return "bg-gradient-to-r from-cyan-500/10 to-emerald-500/5 border-cyan-200/70 text-cyan-950 dark:from-cyan-950/20 dark:to-emerald-950/10 dark:border-cyan-800/40 dark:text-cyan-200 shadow-sm";
  }

  // 6. JD分析 (JD Analysis) - 琥珀橙渐变
  if (id === "jd_analysis") {
    return "bg-gradient-to-r from-amber-500/10 to-orange-500/5 border-amber-250/70 text-amber-950 dark:from-amber-950/20 dark:to-orange-950/10 dark:border-amber-800/40 dark:text-amber-200 shadow-sm";
  }

  // 7. 流程收尾 (Closing) - 中性灰渐变
  if (id === "closing") {
    return "bg-gradient-to-r from-slate-500/10 to-zinc-500/5 border-slate-300 text-slate-800 dark:from-zinc-800/20 dark:to-slate-800/10 dark:border-zinc-700/60 dark:text-zinc-300 shadow-sm";
  }

  // 兜底样式
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
