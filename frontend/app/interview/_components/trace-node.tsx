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
}

export function TraceNode({
  id,
  label,
  title,
  status,
  tokens,
  elapsedMs,
}: TraceNodeProps) {
  const badgeClass = getBadgeClass(id);

  return (
    <div data-testid={`trace-node-${id}`} className="group flex gap-3 py-2.5">
      <div className="flex flex-col items-center gap-1 pt-1">
        {status === "pending" && (
          <div
            data-testid="trace-status-pending"
            className="size-5 flex-shrink-0 rounded-full border border-black/15 bg-white transition-colors duration-300 dark:border-white/15 dark:bg-[#252523]"
          />
        )}
        {status === "running" && (
          <div
            data-testid="trace-status-running"
            className="size-5 flex-shrink-0 animate-spin rounded-full border-2 border-[#534AB7] border-t-transparent"
          />
        )}
        {status === "done" && (
          <div
            data-testid="trace-status-done"
            className="flex size-5 flex-shrink-0 items-center justify-center rounded-full bg-[#1D9E75] text-white shadow-sm shadow-emerald-200 animate-in fade-in zoom-in-50 duration-300"
          >
            <svg
              className="size-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={3}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
        )}
        <div className="mt-1 min-h-[16px] w-px flex-1 bg-black/10 group-last:bg-transparent dark:bg-white/10" />
      </div>

      <div className="min-w-0 flex-1 pb-4">
        <div className="mb-1.5 flex flex-wrap items-center gap-2">
          <span className={`rounded px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider shadow-sm ${badgeClass}`}>
            {label}
          </span>
          <span className="text-xs font-semibold text-[#1a1a18] dark:text-[#e8e6de]">{title}</span>
          {status === "running" && (
            <span className="flex gap-0.5 text-[10px] font-bold text-[#534AB7] animate-pulse">
              <span>●</span>
              <span>●</span>
              <span>●</span>
            </span>
          )}
          {elapsedMs !== undefined && (
            <span className="ml-auto rounded border border-black/5 bg-black/[0.03] px-1.5 py-0.5 font-mono text-[10px] text-black/35 dark:border-white/10 dark:bg-white/[0.04] dark:text-white/35">
              {elapsedMs}ms
            </span>
          )}
        </div>

        {tokens && (
          <div className="space-y-1 whitespace-pre-wrap pl-1 text-xs font-normal leading-relaxed text-black/55 animate-in fade-in slide-in-from-top-1 duration-300 dark:text-white/55">
            {tokens.split("\n").map((line, i) => {
              const trimmed = line.trim();
              if (!trimmed) return null;
              return (
                <div key={i} className="flex gap-2 mt-1">
                  <span className="flex-shrink-0 select-none text-black/20 dark:text-white/20">•</span>
                  <span>
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
  if (id === "master") {
    return "border border-[#DCD9FF] bg-[#EEEDFE] text-[#3C3489] dark:border-[#40398A] dark:bg-[#26215C] dark:text-[#CECBF6]";
  }
  if (id === "memory_search") {
    return "border border-[#BDEAD9] bg-[#E1F5EE] text-[#085041] dark:border-[#0B5B4D] dark:bg-[#04342C] dark:text-[#9FE1CB]";
  }
  if (id === "jd_analysis") {
    return "border border-[#F4D4A1] bg-[#FAEEDA] text-[#633806] dark:border-[#7A4708] dark:bg-[#412402] dark:text-[#FAC775]";
  }
  if (id === "question_gen") {
    return "border border-[#E6D4FF] bg-[#F3EEFF] text-[#4C1D95] dark:border-[#55308D] dark:bg-[#281747] dark:text-[#D9C2FF]";
  }
  return "border border-black/10 bg-black/[0.03] text-black/55 dark:border-white/10 dark:bg-white/[0.04] dark:text-white/55";
}
