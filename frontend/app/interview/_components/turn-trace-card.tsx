"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";
import type { TraceNodeData } from "@/lib/prepare-types";
import { INTERVIEW_NODE_LABELS, INTERVIEW_NODE_TITLES } from "@/lib/interview-chat";
import { AgentTrace } from "./agent-trace";
import { TracePanelShell } from "./trace-panel-shell";

interface TurnTraceCardProps {
  status: "running" | "done";
  nodes: TraceNodeData[];
  turnIndex: number;
  summaryScore?: number;
  isOpening?: boolean;
  error?: string;
  isEmbedded?: boolean;
  hasContent?: boolean;
}

export function TurnTraceCard({
  status,
  nodes,
  turnIndex,
  summaryScore,
  isOpening,
  error,
  isEmbedded = false,
  hasContent = false,
}: TurnTraceCardProps) {
  const [expanded, setExpanded] = useState(status === "running" || nodes.length > 0);

  useEffect(() => {
    if (status === "running" || nodes.length > 0) {
      setExpanded(true);
    }
  }, [status, nodes.length]);

  const isDone = status === "done";
  
  // 核心文案逻辑优化：如果是开场出题卡片，或者 turnIndex === 1（首题生成）
  let headerText = "";
  if (error) {
    headerText = error;
  } else if (isOpening || turnIndex === 1) {
    headerText = isDone ? "AI 面试官 · 准备就绪" : "AI 面试官 · 正在准备题目";
  } else {
    headerText = isDone 
      ? `多 Agent · 分析完成 · 第 ${turnIndex - 1} 轮` 
      : `多 Agent · 正在分析 · 第 ${turnIndex - 1} 轮`;
  }

  return (
    <div className={cn(
      "w-full transition-all duration-300 animate-in fade-in slide-in-from-bottom-2",
      isEmbedded ? "mt-3.5" : "my-2"
    )}>
      {isEmbedded && hasContent && (
        <div className="mb-3.5 border-t border-black/[0.05] dark:border-white/[0.05]" aria-hidden="true" />
      )}
      
      <TracePanelShell
        expanded={expanded}
        title={headerText}
        tone={error ? "error" : isDone ? "success" : "default"}
        toggleText={expanded ? "收起思考过程" : "展开思考过程"}
        onToggle={() => setExpanded((v) => !v)}
        meta={
          <span className="flex shrink-0 items-center gap-2">
            {typeof summaryScore === "number" && !isOpening && turnIndex > 1 && (
              <span className="rounded-full bg-[#534AB7]/10 px-2 py-0.5 font-bold text-[#534AB7] dark:bg-[#cecbf6]/10 dark:text-[#cecbf6] text-[9px]">
                {summaryScore.toFixed(1)} / 10
              </span>
            )}
          </span>
        }
      >
        <div className="mb-2 px-1 text-[11px] font-bold text-black/55 dark:text-white/55">
          {isOpening || turnIndex === 1 ? "AI 思考过程 - 准备阶段" : "AI 思考过程 - 分析与出题"}
        </div>
        <AgentTrace 
          nodes={nodes} 
          nodeTitles={INTERVIEW_NODE_TITLES}
          nodeLabels={INTERVIEW_NODE_LABELS}
        />
      </TracePanelShell>
    </div>
  );
}
