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
}: TraceNodeProps) {
  const badgeClass = getBadgeClass(id);

  return (
    <div data-testid={`trace-node-${id}`} className="group flex gap-3 py-2.5">
      <div className="relative flex flex-col items-center pt-0.5 w-5 flex-shrink-0 self-stretch">
        {/* 垂直 Timeline 连接线 */}
        {!isLast && (
          <div className="absolute top-7 bottom-[-10px] w-[1.5px] bg-gradient-to-b from-[#534AB7]/40 via-[#534AB7]/20 to-transparent dark:from-white/30 dark:via-white/12" />
        )}
        {/* 节点状态 Icon/Dot */}
        <div
          data-testid={`trace-status-${status}`}
          className={`relative z-10 flex h-5 w-5 items-center justify-center rounded-full border-[1.5px] transition-all duration-500 shadow-sm ${
            status === "running"
              ? "animate-pulse border-[#534AB7] bg-white text-[#534AB7] ring-4 ring-[#534AB7]/15 dark:border-[#CECBF6] dark:bg-zinc-950"
              : status === "done"
                ? "border-emerald-500 bg-emerald-50 text-emerald-600 dark:border-emerald-500/60 dark:bg-emerald-500/15 dark:text-emerald-400"
                : "border-[#534AB7]/35 bg-white text-[#534AB7]/50 dark:border-white/20 dark:bg-zinc-950"
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
                  : "bg-[#534AB7]/40 dark:bg-white/20"
              }`}
            />
          )}
        </div>
      </div>

      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <span
              className={`flex-shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-bold tracking-tight transition-all duration-300 ${badgeClass}`}
            >
              {label}
            </span>
            <span className="text-[12px] font-semibold tracking-tight text-black/85 dark:text-white/90 truncate">
              {title}
            </span>
          </div>
          {elapsedMs !== undefined && elapsedMs > 0 && (
            <span className="flex-shrink-0 text-[10px] tabular-nums font-medium text-black/50 dark:text-white/35">
              {elapsedMs}ms
            </span>
          )}
        </div>

        {/* 评估结果徽章：仅在 evaluator 或 chief_think 节点完成时展示 */}
        {(id === "evaluator" || id === "chief_think") && status === "done" && (
          <div className="flex flex-wrap gap-1.5 mb-2.5 animate-in fade-in slide-in-from-top-1 duration-500">
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
            <div className="mb-2.5 pl-2.5 border-l-[1.5px] border-sky-300/50 dark:border-sky-700/40 animate-in fade-in slide-in-from-top-1 duration-500">
              <div className="flex gap-2 items-start p-2 rounded-lg bg-sky-50/70 border border-sky-200/50 dark:bg-sky-950/25 dark:border-sky-800/40">
                <span className="flex-shrink-0 text-[10px] mt-[1px]">📝</span>
                <span className="text-[11px] leading-relaxed text-sky-900/80 dark:text-sky-300/85 font-medium">
                  {designedQuestion}
                </span>
              </div>
            </div>
          )}

        {/* 准备阶段出题节点：不渲染题目详情，仅显示完成提示 */}
        {id === "question_gen" && tokens && (
          <div className="space-y-1.5 pl-2.5 border-l-[1.5px] border-[#534AB7]/20 dark:border-white/15 animate-in fade-in slide-in-from-top-1 duration-500">
            {status === "running" ? (
              <p className="text-[11px] text-[#534AB7]/65 animate-pulse dark:text-[#CECBF6]/65 font-medium">
                正在为你定制专属题目...
              </p>
            ) : (
              <p className="text-[11px] text-emerald-700/85 dark:text-emerald-400/85 font-semibold">
                已为你定制 5 道专属面试题，面试中将逐题呈现。
              </p>
            )}
          </div>
        )}

        {/* 其他节点（如 Master）：展示流式思维链文本，过滤 JSON 特征 */}
        {id !== "question_gen" && tokens && (
          <div className="space-y-1.5 whitespace-pre-wrap pl-2.5 border-l-[1.5px] border-[#534AB7]/20 dark:border-white/15 text-[11px] font-normal leading-relaxed text-black/70 dark:text-white/75 animate-in fade-in slide-in-from-top-1 duration-500">
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
                  <span className="flex-shrink-0 select-none text-[#534AB7]/55 dark:text-[#CECBF6]/55 mt-[3px] font-mono text-[8px]">
                    →
                  </span>
                  <span className="break-words font-medium">
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
