"use client";

import { useEffect, useState } from "react";

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
}

export function TurnTraceCard({
  status,
  nodes,
  turnIndex,
  summaryScore,
  isOpening,
  error,
}: TurnTraceCardProps) {
  const [expanded, setExpanded] = useState(status === "running");

  useEffect(() => {
    if (status === "running") {
      setExpanded(true);
    } else {
      setExpanded(false);
    }
  }, [status]);

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
    <TracePanelShell
      expanded={expanded}
      title={headerText}
      tone={error ? "error" : isDone ? "success" : "default"}
      toggleText={expanded ? "收起思考过程" : "展开思考过程"}
      onToggle={() => setExpanded((v) => !v)}
      className="mx-0 my-2 animate-in fade-in duration-300"
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
      <AgentTrace 
        nodes={nodes} 
        nodeTitles={INTERVIEW_NODE_TITLES}
        nodeLabels={INTERVIEW_NODE_LABELS}
      />
    </TracePanelShell>
  );
}
