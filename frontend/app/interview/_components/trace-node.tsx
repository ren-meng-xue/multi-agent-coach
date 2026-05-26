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
    <div data-testid={`trace-node-${id}`} className="group flex gap-4 py-3">
      <div className="flex flex-col items-center gap-1.5 pt-1">
        {status === "pending" && (
          <div
            data-testid="trace-status-pending"
            className="size-5 flex-shrink-0 flex items-center justify-center rounded-full"
          >
            <div className="size-2 rounded-full border border-black/20 dark:border-white/20 bg-black/[0.02] dark:bg-white/[0.02] transition-colors duration-500" />
          </div>
        )}
        {status === "running" && (
          <div
            data-testid="trace-status-running"
            className="relative flex size-5 flex-shrink-0 items-center justify-center rounded-full bg-[#534AB7]/10 dark:bg-[#CECBF6]/10"
          >
            <div className="absolute inset-0 animate-ping rounded-full bg-[#534AB7]/20 dark:bg-[#CECBF6]/20" />
            <div className="size-2 rounded-full bg-[#534AB7] dark:bg-[#CECBF6] shadow-[0_0_8px_rgba(83,74,183,0.5)] dark:shadow-[0_0_8px_rgba(206,203,246,0.5)]" />
          </div>
        )}
        {status === "done" && (
          <div
            data-testid="trace-status-done"
            className="flex size-5 flex-shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white shadow-[0_2px_8px_-1px_rgba(16,185,129,0.3)] dark:bg-emerald-600 dark:shadow-none animate-in fade-in zoom-in-50 duration-500"
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
                strokeWidth={3.5}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
        )}
        <div className={`mt-1.5 w-[1.5px] flex-1 transition-all duration-700 ${
          status === "running"
            ? "bg-gradient-to-b from-[#534AB7] via-[#7B71F3]/50 to-transparent animate-pulse"
            : status === "done"
            ? "bg-emerald-500/30 dark:bg-emerald-500/20"
            : "bg-black/[0.06] dark:bg-white/[0.06]"
        } group-last:bg-transparent`} />
      </div>

      <div className="min-w-0 flex-1 pb-2">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className={`rounded-md px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-widest shadow-[0_1px_2px_rgba(0,0,0,0.02)] ${badgeClass}`}>
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

        {id === "master" && status === "running" && (
          <p className="pl-2 text-[11px] text-black/30 animate-pulse dark:text-white/30">
            分析中...
          </p>
        )}
        {id !== "master" && tokens && (
          <div className="space-y-1.5 whitespace-pre-wrap pl-2.5 border-l-[1.5px] border-black/[0.04] dark:border-white/[0.04] text-[11px] font-normal leading-relaxed text-black/55 dark:text-white/60 animate-in fade-in slide-in-from-top-1 duration-500">
            {tokens.split("\n").map((line, i) => {
              const trimmed = line.trim();
              if (!trimmed) return null;
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
