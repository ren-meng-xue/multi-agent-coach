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
      className={`w-full rounded-2xl border transition-all duration-300 bg-slate-100/90 border-slate-300/80 dark:bg-zinc-900/65 dark:border-zinc-700/80 shadow-[0_12px_40px_-4px_rgba(0,0,0,0.04)] ${className}`}
    >
      {/* Header 行：可点击折叠/展开，动态显示题目结果 */}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-[#534AB7]/5 dark:hover:bg-white/[0.02] transition-colors duration-200 rounded-t-2xl"
      >
        <span className="relative flex size-1.5 flex-shrink-0 items-center justify-center">
          {tone === "default" && (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#534AB7] opacity-60 dark:bg-[#CECBF6]" />
          )}
          <span
            className={`relative inline-flex size-1.5 rounded-full ${getDotClass(tone)}`}
          />
        </span>
        <span className="text-xs font-bold tracking-tight text-[#534AB7] dark:text-[#CECBF6] line-clamp-1">
          {title}
        </span>
        {meta}
        <span className="ml-1 flex-shrink-0 text-[11px] font-semibold text-[#534AB7]/70 dark:text-[#CECBF6]/75 hover:text-[#534AB7] dark:hover:text-[#CECBF6] transition-colors duration-200">
          ({toggleText})
        </span>
        <svg
          className={`size-3 flex-shrink-0 text-[#534AB7]/70 dark:text-[#CECBF6]/70 transition-transform duration-300 ${expanded ? "rotate-180" : ""}`}
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
