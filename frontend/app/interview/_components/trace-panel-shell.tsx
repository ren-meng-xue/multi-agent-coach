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
    <div className={`w-full bg-transparent transition-all duration-300 ${className}`}>
      <div className="pb-1 mb-2.5">
        <button
          type="button"
          onClick={onToggle}
          className={`inline-flex w-full items-center justify-between gap-3 rounded-lg px-1 py-1 text-[10px] font-bold transition-all hover:underline ${getButtonClass(tone)}`}
        >
          <span className="flex min-w-0 items-center gap-2">
            <span className={`size-1.5 shrink-0 rounded-full ${getDotClass(tone)}`} />
            <span className="truncate">{title}</span>
            {meta}
          </span>
          <span className="shrink-0 text-[9px] opacity-60">{toggleText}</span>
        </button>
      </div>

      {expanded && (
        <div className={`bg-transparent pt-1 pb-2 transition-all duration-300 ${expandedClassName}`}>
          {children}
        </div>
      )}
    </div>
  );
}

function getButtonClass(tone: TracePanelTone) {
  if (tone === "error") {
    return "text-rose-600 hover:text-rose-700 dark:text-rose-400 dark:hover:text-rose-300";
  }

  return "text-black/35 hover:text-[#534AB7] dark:text-white/35 dark:hover:text-[#CECBF6]";
}

function getDotClass(tone: TracePanelTone) {
  if (tone === "success") {
    return "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.4)]";
  }

  if (tone === "error") {
    return "bg-rose-500 shadow-[0_0_6px_rgba(244,63,94,0.4)]";
  }

  return "bg-[#534AB7] shadow-[0_0_0_4px_rgba(83,74,183,0.10)] animate-pulse dark:bg-[#CECBF6] dark:shadow-[0_0_0_4px_rgba(206,203,246,0.12)]";
}
