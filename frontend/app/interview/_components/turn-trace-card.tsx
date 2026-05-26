"use client";

import { useEffect, useState } from "react";

import type { TraceNodeData } from "@/lib/prepare-types";
import { AgentTrace } from "./agent-trace";

interface TurnTraceCardProps {
  status: "running" | "done";
  nodes: TraceNodeData[];
  turnIndex: number;
  summaryScore?: number;
  isOpening?: boolean;
  isEmbedded?: boolean;
}

const INTERVIEW_NODE_TITLES: Record<string, string> = {
  master: "分析表现，规划下一步",
  evaluator: "多维深度评估",
  followup: "生成追问逻辑",
  ask_question: "抽取下一道题",
};

const INTERVIEW_NODE_LABELS: Record<string, string> = {
  master: "调度",
  evaluator: "评估官",
  followup: "面试官",
  ask_question: "出题官",
};

export function TurnTraceCard({
  status,
  nodes,
  turnIndex,
  summaryScore,
  isOpening,
  isEmbedded = false,
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
  if (isOpening || turnIndex === 1) {
    headerText = isDone ? "AI 面试官 · 准备就绪" : "AI 面试官 · 正在准备题目";
  } else {
    headerText = isDone 
      ? `多 Agent · 分析完成 · 第 ${turnIndex - 1} 轮` 
      : `多 Agent · 正在分析 · 第 ${turnIndex - 1} 轮`;
  }

  // 当正在运行 (status === "running") 时，我们追求极致流式！
  if (status === "running") {
    return (
      <div className="w-full mx-0 my-1 bg-transparent transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="flex items-center gap-2 mb-3 px-1 text-[10px] font-bold text-black/40 dark:text-white/35">
          <span className="size-1 rounded-full bg-[#534AB7] dark:bg-[#cecbf6] animate-pulse" />
          <span className="tracking-wider">{headerText.toUpperCase()}</span>
        </div>
        <AgentTrace 
          nodes={nodes} 
          nodeTitles={INTERVIEW_NODE_TITLES}
          nodeLabels={INTERVIEW_NODE_LABELS}
        />
      </div>
    );
  }

  // 当运行完成 (status === "done") 时，我们只渲染极其精细雅致的微缩文本折叠链接
  return (
    <div className="w-full mx-0 my-0 bg-transparent transition-all duration-300">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="inline-flex items-center gap-2 px-1 py-1 text-[10px] font-bold text-black/30 hover:text-[#534AB7] hover:underline dark:text-white/30 dark:hover:text-[#CECBF6] transition-all"
      >
        <span
          className="size-1 rounded-full bg-emerald-500/60"
        />
        <span className="tracking-tight">{headerText}</span>
        {typeof summaryScore === "number" && !isOpening && turnIndex > 1 && (
          <span className="rounded bg-[#534AB7]/5 px-1 py-0.2 font-black text-[8px] tracking-tighter text-[#534AB7]/40 dark:bg-[#cecbf6]/10 dark:text-[#cecbf6]/40">
            {summaryScore.toFixed(1)} / 10
          </span>
        )}
        <span className="text-[9px] opacity-40">
          ({expanded ? "收起思考过程" : "展开思考过程"})
        </span>
      </button>
      
      {expanded && (
        <div className="bg-transparent transition-all duration-300 pt-1 pb-2">
          <AgentTrace 
            nodes={nodes} 
            nodeTitles={INTERVIEW_NODE_TITLES}
            nodeLabels={INTERVIEW_NODE_LABELS}
          />
        </div>
      )}
    </div>
  );
}
