"use client";

import type { TraceNodeData } from "@/lib/prepare-types";
import { PREPARE_NODE_TITLES } from "@/lib/interview-chat";

import { TraceNode } from "./trace-node";

export type { TraceNodeData };

interface AgentTraceProps {
  nodes: TraceNodeData[];
  nodeTitles?: Record<string, string>;
  nodeLabels?: Record<string, string>;
}

export function AgentTrace({ nodes, nodeTitles, nodeLabels }: AgentTraceProps) {
  return (
    <div className="px-1 py-1">
      {nodes.map((node, index) => (
        <TraceNode
          key={node.id}
          id={node.id}
          label={nodeLabels?.[node.id] || (node.id === "master" || node.label === "MASTER" ? "AI面试官" : node.label)}
          title={node.title || nodeTitles?.[node.id] || PREPARE_NODE_TITLES[node.id] || node.id}
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
