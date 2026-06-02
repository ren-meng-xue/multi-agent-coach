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
            <span className="inline-flex items-center gap-0.5 rounded-full bg-[#534AB7]/10 px-2 py-0.5 text-[9px] font-extrabold text-[#534AB7] border border-[#534AB7]/12 dark:bg-[#CECBF6]/10 dark:text-[#CECBF6] dark:border-[#CECBF6]/12">
              <span className="opacity-40 select-none">#</span>
              <span>{direction}</span>
            </span>
          )
        }
      >
        <div className="mb-2.5 px-1 text-[11px] font-extrabold text-[#534AB7] dark:text-[#CECBF6] flex items-center gap-1.5">
          <span className="inline-block size-1.5 bg-[#534AB7] rounded-full dark:bg-[#CECBF6] animate-pulse" />
          <span>AI 思考过程 - 准备阶段</span>
        </div>
        <AgentTrace nodes={nodes} />
      </TracePanelShell>
    </div>
  );
}
