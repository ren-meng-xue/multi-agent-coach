"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";
import type { TraceNodeData } from "@/lib/prepare-types";
import {
  INTERVIEW_NODE_LABELS,
  INTERVIEW_NODE_TITLES,
} from "@/lib/interview-chat";
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
  /** 受控展开状态（嵌入模式由父级控制） */
  expanded?: boolean;
  onToggle?: () => void;
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
  expanded: controlledExpanded,
  onToggle: controlledOnToggle,
}: TurnTraceCardProps) {
  const [internalExpanded, setInternalExpanded] = useState(true);

  const expanded =
    controlledExpanded !== undefined ? controlledExpanded : internalExpanded;
  const onToggle = controlledOnToggle ?? (() => setInternalExpanded((v) => !v));

  const isDone = status === "done";

  // 嵌入模式：无 header，包裹与独立面板完全相同的底色、边框背景，完美解决看板颜色不一致问题
  if (isEmbedded) {
    if (!expanded) return null; // 展开状态关闭时，直接不渲染任何内容，避免留下空的背景和边框占位符
    return (
      <div
        className={cn(
          "w-full transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 mt-3 rounded-xl border bg-slate-100/90 border-slate-300/80 dark:bg-zinc-900/65 dark:border-zinc-700/80 px-4 py-3 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.02)]",
        )}
      >
        <AgentTrace
          nodes={nodes}
          nodeTitles={INTERVIEW_NODE_TITLES}
          nodeLabels={INTERVIEW_NODE_LABELS}
          summaryScore={summaryScore}
        />
      </div>
    );
  }

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
    <div className="w-full transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 my-2">
      <TracePanelShell
        expanded={expanded}
        title={headerText}
        tone={error ? "error" : isDone ? "success" : "default"}
        toggleText={expanded ? "收起思考过程" : "查看 AI 思考过程"}
        onToggle={onToggle}
      >
        <AgentTrace
          nodes={nodes}
          nodeTitles={INTERVIEW_NODE_TITLES}
          nodeLabels={INTERVIEW_NODE_LABELS}
          summaryScore={summaryScore}
        />
      </TracePanelShell>
    </div>
  );
}
