"use client";

import { useEffect, useState } from "react";

import type { TraceNodeData } from "@/lib/prepare-types";
import { AgentTrace } from "./agent-trace";
import { TracePanelShell } from "./trace-panel-shell";

interface PreparationCardProps {
  status: "running" | "done" | "waiting_direction";
  nodes: TraceNodeData[];
  direction?: string;
}

export function PreparationCard({
  status,
  nodes,
  direction,
}: PreparationCardProps) {
  const [expanded, setExpanded] = useState(status === "running" || nodes.length > 0);

  useEffect(() => {
    if (status === "running" || nodes.length > 0) {
      setExpanded(true);
    }
  }, [status, nodes.length]);

  const statusText = status === "running"
    ? "正在调度"
    : status === "done"
    ? "调度中心：准备就绪"
    : "等待方向";

  return (
    <div
      className={
        status === "running"
          ? "w-full mx-0 my-1 bg-transparent transition-all animate-in fade-in slide-in-from-bottom-2 duration-300"
          : "w-full mx-0 my-0 bg-transparent transition-all duration-300"
      }
    >
      <TracePanelShell
        expanded={expanded}
        title={statusText}
        tone={status === "done" ? "success" : "default"}
        toggleText={expanded ? "收起专家组详情" : "展开专家组详情"}
        onToggle={() => setExpanded((v) => !v)}
        meta={
          direction && (
            <span className="text-[10px] font-bold text-[#534AB7] dark:text-[#CECBF6]">
              <span className="opacity-40 mr-0.5 select-none">#</span>
              <span>{direction}</span>
            </span>
          )
        }
      >
        <div className="mb-2 px-1 text-[11px] font-bold text-black/55 dark:text-white/55">
          AI 思考过程 - 准备阶段
        </div>
        <AgentTrace nodes={nodes} />
      </TracePanelShell>
    </div>
  );
}
