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
}: TraceNodeProps) {
  const badgeClass = getBadgeClass(id);

  return (
    <div data-testid={`trace-node-${id}`} className="group flex gap-4 py-3">
      <div className="relative flex flex-col items-center pt-0.5 w-6 flex-shrink-0 self-stretch">
        {/* 垂直 Timeline 连接线：绝对定位并根据图标位置微调起始点 */}
        {!isLast && (
          <div 
            className={`absolute left-1/2 top-[12.5px] w-[1.5px] -translate-x-1/2 bottom-0 transition-all duration-700 ${
              status === "running"
                ? "bg-gradient-to-b from-[#534AB7] via-[#534AB7]/40 to-transparent animate-pulse"
                : status === "done"
                ? "bg-emerald-500/40 dark:bg-emerald-500/25"
                : "bg-black/[0.08] dark:bg-white/[0.08]"
            }`} 
          />
        )}
        
        {/* 状态图标容器 */}
        <div className="relative z-10 flex items-center justify-center">
          {status === "pending" && (
            <div
              data-testid="trace-status-pending"
              className="size-[21px] flex items-center justify-center rounded-full border-[1.5px] border-black/[0.08] dark:border-white/[0.08] bg-black/[0.02] dark:bg-white/[0.02]"
            >
              <div className="size-1 rounded-full bg-black/10 dark:bg-white/10" />
            </div>
          )}
          {status === "running" && (
            <div
              data-testid="trace-status-running"
              className="relative flex size-[21px] items-center justify-center rounded-full border-[1.5px] border-[#534AB7] bg-[#534AB7]/10 dark:bg-[#CECBF6]/10 animate-[traceNodeRunning_1.3s_infinite]"
            >
              <svg
                className="size-2.5 text-[#534AB7] dark:text-[#CECBF6]"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={3}
                  d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                />
              </svg>
            </div>
          )}
          {status === "done" && (
            <div
              data-testid="trace-status-done"
              className="flex size-[21px] items-center justify-center rounded-full bg-emerald-500 text-white shadow-[0_2px_8px_-1px_rgba(16,185,129,0.45)] dark:bg-emerald-600 dark:shadow-none animate-in fade-in zoom-in-50 duration-500"
            >
              <svg
                className="size-2.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={4.5}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
          )}
        </div>
      </div>

      <div className="min-w-0 flex-1 pb-2">
        <div className="flex flex-wrap items-center gap-2 h-[21px] mb-2">
          <span className={`rounded px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-widest ${badgeClass}`}>
            {label}
          </span>
          <span className="text-xs font-bold text-black/85 dark:text-white/85">{title}</span>
          {status === "running" && (
            <span className="flex gap-0.5 text-[8px] text-[#534AB7] dark:text-[#CECBF6] animate-pulse">
              <span>●</span>
              <span>●</span>
              <span>●</span>
            </span>
          )}
          {elapsedMs !== undefined && (
            <span className="ml-auto rounded-md border border-black/[0.04] bg-black/[0.02] px-1.5 py-0.5 font-mono text-[9px] text-black/30 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/30">
              {elapsedMs}ms
            </span>
          )}
        </div>

        {/* 画像 + 信号区域 */}
        {id === "evaluator" && status === "done" && (candidateLevel || latentSignals?.length || missingDimensions?.length) && (
          <div className="mb-2.5 flex flex-wrap gap-1.5 pl-2.5 border-l-[1.5px] border-black/[0.04] dark:border-white/[0.04] animate-in fade-in slide-in-from-top-1 duration-500">
            {candidateLevel && (
              <span className="rounded bg-[#E1F5F2] text-[#0D6B5E] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider">
                {candidateLevel}
              </span>
            )}
            {latentSignals?.map((sig) => (
              <span key={sig} className="rounded bg-[#534AB7]/5 text-[#534AB7]/70 px-1.5 py-0.5 text-[9px] font-medium">
                {sig}
              </span>
            ))}
            {missingDimensions && missingDimensions.length > 0 && (
              <span className="text-[9px] text-rose-500/60 font-medium">缺失：{missingDimensions.join(" · ")}</span>
            )}
          </div>
        )}

        {/* 出题节点：动态解析 JSON 令牌并展示题目列表 */}
        {id === "question_gen" && tokens && (
          <div className="space-y-1.5 pl-2.5 border-l-[1.5px] border-black/[0.04] dark:border-white/[0.04] animate-in fade-in slide-in-from-top-1 duration-500">
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
                  <p className="text-[11px] text-black/30 animate-pulse dark:text-white/30">
                    正在为你定制专属题目...
                  </p>
                );
              }

              return questionItems.map((item, i) => (
                <div key={i} className="flex gap-2 items-start mt-2 animate-in fade-in slide-in-from-left-2 duration-300">
                  <span className="flex-shrink-0 select-none text-black/25 dark:text-white/25 mt-[3px] font-mono text-[8px]">→</span>
                  <p className="text-[11px] leading-relaxed break-words">
                    {item!.category && (
                      <span className="mr-1.5 inline-flex items-center rounded bg-[#534AB7]/5 px-1 py-0.5 text-[9px] font-black text-[#534AB7]/50 dark:bg-[#CECBF6]/5 dark:text-[#CECBF6]/50 uppercase tracking-tighter">
                        {item!.category === "technical" ? "技术" : item!.category === "behavioral" ? "行为" : "系统设计"}
                      </span>
                    )}
                    <span className="font-medium text-black/65 dark:text-white/70">
                      {item!.text}
                    </span>
                  </p>
                </div>
              ));
            })()}
            {/* 兜底：如果解析不到题目但有大量文本，显示提示 */}
            {status === "done" && Array.from(tokens.matchAll(/question/g)).length === 0 && tokens.length > 50 && (
              <p className="text-[11px] text-black/30 italic">题目已生成，请点击下方「先看题目列表」查看详情。</p>
            )}
          </div>
        )}

        {/* 其他节点（如 Master）：展示流式思维链文本，过滤 JSON 特征 */}
        {id !== "question_gen" && tokens && (
          <div className="space-y-1.5 whitespace-pre-wrap pl-2.5 border-l-[1.5px] border-black/[0.04] dark:border-white/[0.04] text-[11px] font-normal leading-relaxed text-black/55 dark:text-white/60 animate-in fade-in slide-in-from-top-1 duration-500">
            {tokens.split("\n").map((line, i) => {
              const trimmed = line.trim();
              if (!trimmed) return null;
              // 彻底过滤掉可能误出的 JSON 标记
              if (trimmed.startsWith("[") || trimmed.startsWith("{") || trimmed.includes('": "')) return null;
              return (
                <div key={i} className="flex gap-2 items-start mt-1.5 animate-in fade-in slide-in-from-left-2 duration-300">
                  <span className="flex-shrink-0 select-none text-black/25 dark:text-white/25 mt-[3px] font-mono text-[8px]">→</span>
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

function getBadgeClass(id: string) {
  // 1. 核心调度 (Master) - 幽静紫
  if (id === "master") {
    return "border border-[#E2E0FF] bg-[#EEEDFE] text-[#3C3489] dark:border-[#3C3489] dark:bg-[#26215C] dark:text-[#CECBF6]";
  }
  
  // 2. 出题专家 (Question Gen / Ask Question) - 天空蓝
  if (id === "question_gen" || id === "ask_question") {
    return "border border-[#D2E9FF] bg-[#EBF5FF] text-[#1E3A8A] dark:border-[#1E3A8A] dark:bg-[#1E293B] dark:text-[#93C5FD]";
  }

  // 3. 评估专家 (Evaluator) - 薄荷绿
  if (id === "evaluator") {
    return "border border-[#C2F0E7] bg-[#E1F5F2] text-[#0D6B5E] dark:border-[#0D6B5E] dark:bg-[#0A3D36] dark:text-[#A1E6D9]";
  }

  // 4. 面试专家/追问 (Followup) - 蔷薇粉
  if (id === "followup") {
    return "border border-[#FCE7F3] bg-[#FDF2F8] text-[#9D174D] dark:border-[#9D174D] dark:bg-[#500724] dark:text-[#F9A8D4]";
  }

  // 5. 记忆检索 (Memory Search) - 翡翠绿
  if (id === "memory_search") {
    return "border border-[#BDEAD9] bg-[#E1F5EE] text-[#085041] dark:border-[#0B5B4D] dark:bg-[#04342C] dark:text-[#9FE1CB]";
  }

  // 6. JD分析 (JD Analysis) - 琥珀橙
  if (id === "jd_analysis") {
    return "border border-[#F4D4A1] bg-[#FAEEDA] text-[#633806] dark:border-[#7A4708] dark:bg-[#412402] dark:text-[#FAC775]";
  }

  // 7. 流程收尾 (Closing) - 中性灰
  if (id === "closing") {
    return "border border-black/10 bg-black/5 text-black/60 dark:border-white/10 dark:bg-white/5 dark:text-white/60";
  }

  // 兜底样式
  return "border border-black/10 bg-black/[0.03] text-black/55 dark:border-white/10 dark:bg-white/[0.04] dark:text-white/55";
}
