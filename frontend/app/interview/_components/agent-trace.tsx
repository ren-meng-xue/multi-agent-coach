"use client";

import type { TraceNodeData } from "@/lib/prepare-types";

import { TraceNode } from "./trace-node";

export type { TraceNodeData };

interface AgentTraceProps {
  nodes: TraceNodeData[];
  nodeTitles?: Record<string, string>;
  nodeLabels?: Record<string, string>;
}

const DEFAULT_NODE_TITLES: Record<string, string> = {
  master: "识别方向，启动准备",
  memory_search: "读取你的历史表现",
  jd_analysis: "构建考点地图",
  question_gen: "定制专属题目",
};

export function AgentTrace({ nodes, nodeTitles, nodeLabels }: AgentTraceProps) {
  return (
    <div className="px-1 py-1">
      {nodes.map((node, index) => (
        <TraceNode
          key={node.id}
          id={node.id}
          label={nodeLabels?.[node.id] || (node.id === "master" || node.label === "MASTER" ? "AI面试官" : node.label)}
          title={node.title || nodeTitles?.[node.id] || DEFAULT_NODE_TITLES[node.id] || node.id}
          status={node.status}
          tokens={node.tokens}
          elapsedMs={node.elapsedMs}
          isLast={index === nodes.length - 1}
          candidateLevel={node.candidateLevel}
          latentSignals={node.latentSignals}
          missingDimensions={node.missingDimensions}
        />
      ))}
    </div>
  );
}
