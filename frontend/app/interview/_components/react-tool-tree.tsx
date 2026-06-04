"use client";

import { useState } from "react";
import type { ReactIteration } from "@/lib/prepare-types";
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

export function ReactToolTree({
  steps,
  isFinished,
}: {
  steps: ReactIteration[];
  isFinished?: boolean;
}) {
  const [userToggled, setUserToggled] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  if (!steps || steps.length === 0) return null;

  // running 时默认展开，done 后默认折叠；用户手动操作覆盖默认
  const effectiveExpanded = userToggled ? isExpanded : !isFinished;

  function onToggle() {
    setIsExpanded(!effectiveExpanded);
    setUserToggled(true);
  }

  return (
    <div className="mt-2" data-testid="react-tool-tree">
      <button
        onClick={onToggle}
        className="flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-zinc-200 transition-colors"
      >
        {effectiveExpanded ? (
          <ChevronDown className="h-3.5 w-3.5" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5" />
        )}
        {effectiveExpanded ? "收起" : "展开"} ReAct 思考链
      </button>

      {effectiveExpanded && (
        <div className="flex flex-col gap-2 mt-2">
          {steps.map((step) => (
            <IterationCard key={step.index} step={step} />
          ))}
        </div>
      )}
    </div>
  );
}

function IterationCard({ step }: { step: ReactIteration }) {
  return (
    <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 dark:border-zinc-700/60 dark:bg-zinc-900/40 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-200/60 dark:border-zinc-700/40">
        <div className="h-[2px] w-4 bg-[#534AB7]/30 dark:bg-[#CECBF6]/25 rounded-full" />
        <span className="text-[11px] font-bold text-slate-600 dark:text-zinc-300">
          第 {step.index + 1} 轮
        </span>
        <div className="flex-1 h-[1px] bg-slate-200/60 dark:bg-zinc-700/40" />
        {step.thinkStatus === "running" && (
          <Loader2
            className="h-3 w-3 animate-spin text-[#534AB7]/70"
            data-testid="think-spinner"
          />
        )}
      </div>

      <div className="px-3 py-2.5 flex flex-col gap-2.5">
        {step.thinkContent && (
          <div className="flex gap-2 items-start">
            <span className="flex-shrink-0 text-sm leading-tight">💭</span>
            <span className="text-xs text-slate-600 dark:text-zinc-400 whitespace-pre-wrap leading-relaxed">
              {step.thinkContent}
            </span>
          </div>
        )}

        {step.toolCalls.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {step.toolCalls.map((tc) => (
              <div
                key={tc.stepId}
                data-testid={`tool-call-${tc.toolName}`}
                className="flex flex-col gap-0.5"
              >
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="flex-shrink-0 text-sm leading-tight">
                    🔧
                  </span>
                  <span className="font-mono text-[11px] font-semibold text-slate-700 dark:text-zinc-300">
                    {tc.toolName}
                  </span>
                  {tc.argsSummary && (
                    <span className="font-mono text-[11px] text-slate-500 dark:text-zinc-500 truncate flex-1 min-w-0">
                      ({tc.argsSummary})
                    </span>
                  )}
                  <div className="flex-shrink-0 ml-auto pl-2">
                    {tc.status === "running" && (
                      <Loader2
                        className="h-3 w-3 animate-spin text-blue-500"
                        data-testid="tool-spinner"
                      />
                    )}
                    {tc.status === "done" && (
                      <span className="flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400 font-medium tabular-nums">
                        <CheckCircle2 className="h-3 w-3" />
                        {tc.elapsedMs !== undefined
                          ? `${(tc.elapsedMs / 1000).toFixed(1)}s`
                          : ""}
                      </span>
                    )}
                    {tc.status === "error" && (
                      <span className="flex items-center gap-1 text-[10px] text-red-600 dark:text-red-400 font-medium">
                        <AlertCircle className="h-3 w-3" />
                        {tc.elapsedMs !== undefined
                          ? `${(tc.elapsedMs / 1000).toFixed(1)}s`
                          : ""}
                      </span>
                    )}
                  </div>
                </div>
                {tc.resultSummary && (
                  <div className="pl-7 font-mono text-[11px] text-slate-500 dark:text-zinc-500">
                    ↳ {tc.resultSummary}
                  </div>
                )}
                {tc.error && (
                  <div className="pl-7 font-mono text-[11px] text-red-600 dark:text-red-400">
                    ↳ {tc.error}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
