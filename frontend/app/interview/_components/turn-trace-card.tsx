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

  // 嵌入模式：无 header，content 直接渲染，外层气泡已显示题目
  if (isEmbedded) {
    return (
      <div
        className={cn(
          "w-full transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 mt-3.5",
        )}
      >
        {hasContent && (
          <div
            className="mb-3.5 border-t border-black/[0.05] dark:border-white/[0.05]"
            aria-hidden="true"
          />
        )}
        {expanded && (
          <AgentTrace
            nodes={nodes}
            nodeTitles={INTERVIEW_NODE_TITLES}
            nodeLabels={INTERVIEW_NODE_LABELS}
          />
        )}
      </div>
    );
  }

  // 独立模式：完整 TracePanelShell（含 header）
  const designedQuestion = nodes.find(
    (n) => n.designedQuestion,
  )?.designedQuestion;

  let headerText = "";
  if (error) {
    headerText = error;
  } else if (designedQuestion && isDone) {
    headerText = designedQuestion;
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
        toggleText={expanded ? "收起依据" : "查看依据"}
        onToggle={onToggle}
        meta={
          <span className="flex shrink-0 items-center gap-2">
            {typeof summaryScore === "number" &&
              !isOpening &&
              turnIndex > 1 && (
                <span className="rounded-full bg-[#534AB7]/10 px-2.5 py-0.5 font-extrabold text-[#534AB7] border border-[#534AB7]/15 dark:bg-[#cecbf6]/10 dark:text-[#cecbf6] dark:border-[#cecbf6]/15 text-[9px] shadow-sm">
                  评分：{summaryScore.toFixed(1)} / 10
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
    </div>
  );
}
