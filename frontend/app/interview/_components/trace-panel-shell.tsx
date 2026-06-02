"use client";

import type { ReactNode } from "react";

type TracePanelTone = "default" | "success" | "error";

interface TracePanelShellProps {
  expanded: boolean;
  title: string;
  toggleText: string;
  tone: TracePanelTone;
  onToggle: () => void;
  children?: ReactNode;
  meta?: ReactNode;
  className?: string;
  expandedClassName?: string;
}

export function TracePanelShell({
  expanded,
  title,
  toggleText,
  tone,
  onToggle,
  children,
  meta,
  className = "",
  expandedClassName = "",
}: TracePanelShellProps) {
  return (
    <div
      className={`w-full rounded-2xl border transition-all duration-300 ${
        tone === "success"
          ? "bg-[#E8F8F5]/30 border-emerald-500/20 dark:bg-emerald-950/5 dark:border-emerald-500/15 shadow-[0_4px_20px_-4px_rgba(16,185,129,0.06)]"
          : tone === "error"
            ? "bg-[#FDF2F4]/30 border-rose-500/20 dark:bg-rose-950/5 dark:border-rose-500/15 shadow-[0_4px_20px_-4px_rgba(244,63,94,0.06)]"
            : "bg-[#534AB7]/[0.015] border-[#534AB7]/10 dark:bg-white/[0.01] dark:border-white/[0.06] shadow-[0_4px_24px_-4px_rgba(83,74,183,0.04)]"
      } ${className}`}
    >
      {/* Header 行：可点击折叠/展开，动态显示题目结果 */}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-black/[0.01] dark:hover:bg-white/[0.01] transition-colors duration-200 rounded-t-2xl"
      >
        <span className="relative flex size-1.5 flex-shrink-0 items-center justify-center">
          {tone === "default" && (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#534AB7] opacity-60 dark:bg-[#CECBF6]" />
          )}
          <span
            className={`relative inline-flex size-1.5 rounded-full ${getDotClass(tone)}`}
          />
        </span>
        <span className="flex-1 text-[10px] font-extrabold tracking-tight text-[#534AB7]/70 dark:text-[#CECBF6]/70 line-clamp-1">
          {title}
        </span>
        {meta}
        <span className="ml-1 flex-shrink-0 text-[9px] font-medium text-[#534AB7]/30 dark:text-[#CECBF6]/25">
          ({toggleText})
        </span>
        <svg
          className={`size-3 flex-shrink-0 text-[#534AB7]/30 dark:text-[#CECBF6]/25 transition-transform duration-300 ${expanded ? "rotate-180" : ""}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* 内容区：默认展开 */}
      {expanded && (
        <div
          className={`px-4 pb-4 transition-all duration-300 ${expandedClassName}`}
        >
          {children}
        </div>
      )}
    </div>
  );
}

function getDotClass(tone: TracePanelTone) {
  if (tone === "success") {
    return "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)]";
  }

  if (tone === "error") {
    return "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.7)]";
  }

  return "bg-[#534AB7] dark:bg-[#CECBF6] shadow-[0_0_6px_rgba(83,74,183,0.5)]";
}
