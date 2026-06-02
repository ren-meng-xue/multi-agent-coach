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
}: TraceNodeProps) {
  const badgeClass = getBadgeClass(id);

  return (
    <div data-testid={`trace-node-${id}`} className="group flex gap-3.5 py-2.5">
      <div className="relative flex flex-col items-center pt-0.5 w-5 flex-shrink-0 self-stretch">
        {/* 垂直 Timeline 连接线 */}
        {!isLast && (
          <div 
            className={`absolute left-1/2 top-[10.5px] w-[1.5px] -translate-x-1/2 bottom-0 transition-all duration-700 ${
              status === "running"
                ? "bg-gradient-to-b from-[#534AB7] via-[#CECBF6]/50 to-transparent animate-pulse"
                : status === "done"
                ? "bg-emerald-500/40 dark:bg-emerald-500/30"
                : "bg-black/[0.06] dark:bg-white/[0.06]"
            }`} 
          />
        )}
        
        {/* 状态图标容器 */}
        <div 
          className="relative z-10 flex items-center justify-center" 
          data-testid={`trace-status-${status}`}
        >
          {status === "pending" && (
            <div className="size-[18px] flex items-center justify-center rounded-full border border-black/10 bg-black/[0.02] dark:border-white/10 dark:bg-white/[0.02]">
              <div className="size-1 rounded-full bg-black/20 dark:bg-white/30" />
            </div>
          )}
          {status === "running" && (
            <div className="relative size-[18px] flex items-center justify-center">
              {/* 精致的双层发光呼吸涟漪 */}
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#534AB7]/25 opacity-75" />
              <div className="relative size-3.5 flex items-center justify-center rounded-full border border-[#534AB7]/40 bg-[#534AB7]/10 shadow-[0_0_8px_rgba(83,74,183,0.3)]">
                <div className="size-1 rounded-full bg-[#534AB7] dark:bg-[#CECBF6]" />
              </div>
            </div>
          )}
          {status === "done" && (
            <div className="flex size-[18px] items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 shadow-[0_0_8px_rgba(16,185,129,0.25)]">
              <svg className="size-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={4.5} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          )}
        </div>
      </div>

      <div className="min-w-0 flex-1 pb-1">
        <div className="flex flex-wrap items-center gap-2 h-[18px] mb-1.5">
          <span className={`rounded px-1.5 py-0.5 text-[8px] font-extrabold uppercase tracking-wider ${badgeClass}`}>
            {label}
          </span>
          <span className="text-[11px] font-extrabold text-black/80 dark:text-white/90">{title}</span>
          {elapsedMs !== undefined && (
            <span className="ml-auto font-mono text-[8px] text-black/30 dark:text-white/30 font-bold">
              {elapsedMs}ms
            </span>
          )}
        </div>

        {/* 画像 + 信号区域 */}
        {(id === "evaluator" || id === "chief_think") && status === "done" && (candidateLevel || latentSignals?.length || missingDimensions?.length) && (
          <div className="mb-2.5 flex flex-wrap gap-1.5 pl-2.5 border-l-[1.5px] border-[#534AB7]/10 dark:border-white/10 animate-in fade-in slide-in-from-top-1 duration-500">
            {candidateLevel && (
              <span className="rounded bg-teal-50 text-teal-700 border border-teal-100/50 px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wider dark:bg-teal-950/30 dark:text-teal-300">
                {candidateLevel}
              </span>
            )}
            {latentSignals?.map((sig) => (
              <span key={sig} className="rounded bg-[#534AB7]/6 text-[#534AB7] border border-[#534AB7]/10 px-1.5 py-0.5 text-[9px] font-bold dark:bg-[#CECBF6]/6 dark:text-[#CECBF6]">
                {sig}
              </span>
            ))}
            {missingDimensions && missingDimensions.length > 0 && (
              <span className="text-[9px] text-rose-500/70 border border-rose-100/30 bg-rose-50/20 rounded px-1.5 py-0.5 font-bold">
                缺失：{missingDimensions.join(" · ")}
              </span>
            )}
          </div>
        )}

        {id === "chief_think" && status === "done" && chiefToolCalls && chiefToolCalls.length > 0 && (
          <div className="mb-2.5 flex flex-wrap gap-1.5 pl-2.5 border-l-[1.5px] border-[#534AB7]/10 dark:border-white/10 animate-in fade-in slide-in-from-top-1 duration-500">
            {chiefToolCalls.map((tool) => (
              <span
                key={tool}
                className="rounded bg-sky-50 text-sky-700 border border-sky-100/70 px-1.5 py-0.5 text-[9px] font-extrabold dark:bg-sky-950/30 dark:text-sky-300 dark:border-sky-900/40"
              >
                {formatChiefToolName(tool)}
              </span>
            ))}
          </div>
        )}

        {/* 出题节点：动态解析 JSON 令牌并展示题目列表 */}
        {id === "question_gen" && tokens && (
          <div className="space-y-2 pl-2.5 border-l-[1.5px] border-[#534AB7]/10 dark:border-white/10 animate-in fade-in slide-in-from-top-1 duration-500">
            {(() => {
              // 极度鲁棒的解析逻辑：支持跨行匹配 ([\s\S]*?)
              const robustPattern = /["']?question["']?\s*:\s*["']((?:[^"'\\]|\\?[\s\S])*?)(?:["']|$)/gi;
              const matches = Array.from(tokens.matchAll(robustPattern));
              
              const questionItems = matches.map((match, i) => {
                const rawText = match[1].replace(/\\"/g, '"').replace(/\\n/g, ' ').trim();
                if (!rawText || rawText.length < 2) return null;

                // 在当前题目附近寻找分类信息
                const startSearch = Math.max(0, match.index! - 150);
                const endSearch = Math.min(tokens.length, match.index! + match[0].length + 150);
                const contextSnippet = tokens.substring(startSearch, endSearch);
                const categoryMatch = /["']?category["']?\s*:\s*["']([^"']*?)["']/.exec(contextSnippet);
                const category = categoryMatch?.[1];

                return { text: rawText, category };
              }).filter(Boolean);

              if (questionItems.length === 0 && status === "running") {
                return (
                  <p className="text-[11px] text-[#534AB7]/60 animate-pulse dark:text-[#CECBF6]/60 font-medium">
                    正在为你定制专属题目...
                  </p>
                );
              }

              return questionItems.map((item, i) => (
                <div 
                  key={i} 
                  className="flex gap-2 items-start mt-2 p-2.5 rounded-xl bg-white border border-slate-100/90 shadow-[0_2px_8px_rgba(83,74,183,0.02)] hover:border-slate-200/80 hover:shadow-[0_4px_12px_rgba(83,74,183,0.04)] transition-all duration-300 dark:bg-zinc-900/30 dark:border-zinc-800/50 dark:hover:border-zinc-700/50 animate-in fade-in slide-in-from-left-2 duration-300"
                >
                  <span className="flex-shrink-0 select-none text-[#534AB7]/35 dark:text-[#CECBF6]/35 mt-[3px] font-mono text-[8px]">→</span>
                  <div className="text-[11px] leading-relaxed break-words flex-1">
                    {item!.category && (
                      <span className={`mr-2 inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-tight border ${
                        item!.category === "technical"
                          ? "bg-blue-50 text-blue-600 border-blue-100 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900/30"
                          : item!.category === "behavioral"
                          ? "bg-amber-50 text-amber-600 border-amber-100 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/30"
                          : "bg-purple-50 text-purple-600 border-purple-100 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-900/30"
                      }`}>
                        {item!.category === "technical" ? "技术" : item!.category === "behavioral" ? "行为" : "系统设计"}
                      </span>
                    )}
                    <span className="font-semibold text-black/75 dark:text-white/85">
                      {item!.text}
                    </span>
                  </div>
                </div>
              ));
            })()}
            {/* 兜底：如果解析不到题目但有大量文本，显示提示 */}
            {status === "done" && Array.from(tokens.matchAll(/question/g)).length === 0 && tokens.length > 50 && (
              <p className="text-[11px] text-black/40 italic">题目已生成，请点击下方「先看题目列表」查看详情。</p>
            )}
          </div>
        )}

        {/* 其他节点（如 Master）：展示流式思维链文本，过滤 JSON 特征 */}
        {id !== "question_gen" && tokens && (
          <div className="space-y-1.5 whitespace-pre-wrap pl-2.5 border-l-[1.5px] border-[#534AB7]/10 dark:border-white/10 text-[11px] font-normal leading-relaxed text-black/65 dark:text-white/70 animate-in fade-in slide-in-from-top-1 duration-500">
            {tokens.split("\n").map((line, i) => {
              const trimmed = line.trim();
              if (!trimmed) return null;
              // 彻底过滤掉可能误出的 JSON 标记
              if (trimmed.startsWith("[") || trimmed.startsWith("{") || trimmed.includes('": "')) return null;
              return (
                <div key={i} className="flex gap-2 items-start mt-1.5 animate-in fade-in slide-in-from-left-2 duration-300">
                  <span className="flex-shrink-0 select-none text-[#534AB7]/40 dark:text-[#CECBF6]/40 mt-[3px] font-mono text-[8px]">→</span>
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
  // 1. 核心调度 (Master) - 幽静紫
  if (id === "master" || id === "chief_think") {
    return "border border-violet-100 bg-gradient-to-r from-violet-50 to-indigo-50 text-indigo-700 dark:border-indigo-900/50 dark:from-indigo-950/40 dark:to-violet-950/40 dark:text-indigo-300";
  }
  
  // 2. 出题专家 (Question Gen / Ask Question) - 天空蓝
  if (id === "question_gen" || id === "ask_question") {
    return "border border-blue-100 bg-gradient-to-r from-blue-50 to-sky-50 text-blue-700 dark:border-blue-900/50 dark:from-blue-950/40 dark:to-sky-950/40 dark:text-blue-300";
  }

  // 3. 评估专家 (Evaluator) - 薄荷绿
  if (id === "evaluator") {
    return "border border-emerald-100 bg-gradient-to-r from-emerald-50 to-teal-50 text-teal-700 dark:border-teal-900/50 dark:from-teal-950/40 dark:to-emerald-950/40 dark:text-teal-300";
  }

  // 4. 面试专家/追问 (Followup) - 蔷薇粉
  if (id === "followup") {
    return "border border-pink-100 bg-gradient-to-r from-pink-50 to-rose-50 text-pink-700 dark:border-pink-900/50 dark:from-pink-950/40 dark:to-rose-950/40 dark:text-pink-300";
  }

  // 5. 记忆检索 (Memory Search) - 翡翠绿
  if (id === "memory_search") {
    return "border border-cyan-100 bg-gradient-to-r from-cyan-50 to-emerald-50 text-cyan-700 dark:border-cyan-900/50 dark:from-cyan-950/40 dark:to-emerald-950/40 dark:text-cyan-300";
  }

  // 6. JD分析 (JD Analysis) - 琥珀橙
  if (id === "jd_analysis") {
    return "border border-amber-100 bg-gradient-to-r from-amber-50 to-orange-50 text-amber-700 dark:border-amber-900/50 dark:from-amber-950/40 dark:to-orange-950/40 dark:text-amber-300";
  }

  // 7. 流程收尾 (Closing) - 中性灰
  if (id === "closing") {
    return "border border-slate-200 bg-slate-50 text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400";
  }

  // 兜底样式
  return "border border-slate-100 bg-slate-50/50 text-slate-500 dark:border-zinc-800 dark:bg-zinc-900/20 dark:text-zinc-400";
}
