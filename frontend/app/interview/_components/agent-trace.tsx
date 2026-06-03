"use client";

import type { TraceNodeData } from "@/lib/prepare-types";
import { PREPARE_NODE_TITLES } from "@/lib/interview-chat";

import { TraceNode } from "./trace-node";

export type { TraceNodeData };

interface AgentTraceProps {
  nodes: TraceNodeData[];
  nodeTitles?: Record<string, string>;
  nodeLabels?: Record<string, string>;
  summaryScore?: number;
}

export function AgentTrace({ nodes, nodeTitles, nodeLabels, summaryScore }: AgentTraceProps) {
  return (
    <div className="px-1 py-1">
      {nodes.map((node, index) => {
        const label = node.label === "MASTER"
          ? nodeLabels?.[node.id] || "调度"
          : node.label || nodeLabels?.[node.id] || node.id;

        return (
          <TraceNode
            key={node.id}
            id={node.id}
            label={label}
            title={node.title || nodeTitles?.[node.id] || PREPARE_NODE_TITLES[node.id] || node.id}
            status={node.status}
            tokens={node.tokens}
            elapsedMs={node.elapsedMs}
            isLast={index === nodes.length - 1}
            candidateLevel={node.candidateLevel}
            latentSignals={node.latentSignals}
            missingDimensions={node.missingDimensions}
            chiefToolCalls={node.chiefToolCalls}
            designedQuestion={node.designedQuestion}
            designedCategory={node.designedCategory}
            designedSource={node.designedSource}
            summaryScore={node.summaryScore ?? (node.id === "evaluator" ? summaryScore : undefined)}
          />
        );
      })}
    </div>
  );
}
