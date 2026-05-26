"use client";

import { useEffect, useState } from "react";

import type { TraceNodeData } from "@/lib/prepare-types";
import { AgentTrace } from "./agent-trace";

interface TurnTraceCardProps {
  status: "running" | "done";
  nodes: TraceNodeData[];
  turnIndex: number;
  summaryScore?: number;
}

export function TurnTraceCard({ status, nodes, turnIndex, summaryScore }: TurnTraceCardProps) {
  const [expanded, setExpanded] = useState(status === "running");

  useEffect(() => {
    if (status === "running") {
      setExpanded(true);
    } else {
      setExpanded(false);
    }
  }, [status]);

  const isDone = status === "done";
  const headerText = isDone ? "本轮分析完成" : "本轮分析中";

  return (
    <div className="mx-0 mt-1 overflow-hidden rounded-xl border border-black/10 bg-white shadow-sm animate-in fade-in duration-300 dark:border-white/10 dark:bg-[#1c1c1a]">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between border-b border-black/10 bg-[#f7f6f2] px-4 py-3 dark:border-white/10 dark:bg-[#252523]"
      >
        <div className="flex items-center gap-2">
          <span
            className={`size-2 rounded-full flex-shrink-0 transition-all duration-300 ${
              isDone ? "bg-[#1D9E75]" : "bg-[#534AB7] animate-pulse shadow-[0_0_0_4px_rgba(83,74,183,0.12)]"
            }`}
          />
          <span className="text-xs font-bold text-[#1a1a18] dark:text-[#e8e6de]">
            {headerText} · 第 {turnIndex} 轮
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-[#8a8a8a]">
          {typeof summaryScore === "number" && (
            <span className="rounded-full bg-[#eef2ff] px-2 py-0.5 font-semibold text-[#4f46e5]">
              {summaryScore.toFixed(1)} / 10
            </span>
          )}
          <span>{expanded ? "收起" : "展开"}</span>
        </div>
      </button>
      {expanded && <AgentTrace nodes={nodes} />}
    </div>
  );
}
