"use client";

import { TraceNode, type TraceNodeStatus } from "./trace-node";

export type TraceNodeData = {
  id: string;
  label: string;
  title?: string;
  status: TraceNodeStatus;
  tokens: string;
  elapsedMs?: number;
};

interface AgentTraceProps {
  nodes: TraceNodeData[];
}

const NODE_TITLES: Record<string, string> = {
  master: "识别方向，启动准备",
  memory_search: "读取你的历史表现",
  jd_analysis: "构建考点地图",
  question_gen: "定制专属题目",
};

export function AgentTrace({ nodes }: AgentTraceProps) {
  return (
    <div className="px-5 py-3">
      {nodes.map((node) => (
        <TraceNode
          key={node.id}
          id={node.id}
          label={node.label}
          title={node.title || NODE_TITLES[node.id] || node.id}
          status={node.status}
          tokens={node.tokens}
          elapsedMs={node.elapsedMs}
        />
      ))}
    </div>
  );
}
