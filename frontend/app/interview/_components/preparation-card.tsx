"use client";

import { useEffect, useState } from "react";

import type { TraceNodeData } from "@/lib/prepare-types";
import { AgentTrace } from "./agent-trace";
import { TracePanelShell } from "./trace-panel-shell";

interface PreparationCardProps {
  status: "running" | "done" | "waiting_direction";
  nodes: TraceNodeData[];
  direction?: string;
  summary?: string;
}

export function PreparationCard({
  status,
  nodes,
  direction,
  summary,
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
      >
        <AgentTrace nodes={nodes} />
        {summary && (
          <div className="animate-in fade-in duration-500">
            <div className="border-t border-dashed border-slate-200 my-4" />
            <div className="bg-[#fafaf9] border border-[#e7e5e4] rounded-xl p-3 mt-0">
              <div className="flex items-center gap-1.5 mb-2">
                <div className="w-4 h-4 rounded-full bg-[#1e293b] shrink-0" />
                <span className="text-[10px] font-bold text-[#44403c]">
                  准备完成 · AI 综合判断
                </span>
              </div>
              <p className="text-xs text-[#57534e] leading-relaxed whitespace-pre-wrap">
                {summary}
              </p>
            </div>
          </div>
        )}
      </TracePanelShell>
    </div>
  );
}
