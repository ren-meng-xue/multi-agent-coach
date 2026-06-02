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
      className={`w-full rounded-2xl border transition-all duration-300 p-4 ${
        tone === "success"
          ? "bg-[#E8F8F5]/30 border-emerald-500/20 dark:bg-emerald-950/5 dark:border-emerald-500/15 shadow-[0_4px_20px_-4px_rgba(16,185,129,0.06)]"
          : tone === "error"
          ? "bg-[#FDF2F4]/30 border-rose-500/20 dark:bg-rose-950/5 dark:border-rose-500/15 shadow-[0_4px_20px_-4px_rgba(244,63,94,0.06)]"
          : "bg-[#534AB7]/[0.015] border-[#534AB7]/10 dark:bg-white/[0.01] dark:border-white/[0.06] shadow-[0_4px_24px_-4px_rgba(83,74,183,0.04)]"
      } ${className}`}
    >
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onToggle}
          className={`group/btn inline-flex items-center gap-2 rounded-full px-3 py-1 text-[10px] font-extrabold tracking-tight transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] ${
            tone === "success"
              ? "bg-emerald-500/10 text-emerald-700 border border-emerald-500/15 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/15 hover:bg-emerald-500/20"
              : tone === "error"
              ? "bg-rose-500/10 text-rose-700 border border-rose-500/15 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/15 hover:bg-rose-500/20"
              : "bg-[#534AB7]/8 text-[#534AB7] border border-[#534AB7]/12 dark:bg-[#CECBF6]/8 dark:text-[#CECBF6] dark:border-[#CECBF6]/12 hover:bg-[#534AB7]/15"
          }`}
        >
          <span className="relative flex size-1.5 items-center justify-center">
            {/* 呼吸灯波纹动画 (当处于 active/default 状态时) */}
            {tone === "default" && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#534AB7] opacity-60 dark:bg-[#CECBF6]" />
            )}
            <span className={`relative inline-flex size-1.5 rounded-full ${getDotClass(tone)}`} />
          </span>
          <span className="font-extrabold leading-none">{title}</span>
          {meta}
          <span className="ml-1 text-[9px] font-medium opacity-45 group-hover/btn:opacity-75 transition-opacity">
            ({toggleText})
          </span>
        </button>
      </div>

      {expanded && (
        <div className={`pt-3.5 pb-0.5 transition-all duration-300 ${expandedClassName}`}>
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
