"use client";

import { useEffect, useState } from "react";

import type { PreparedQuestion, JDContext } from "@/lib/prepare-types";
import { AgentTrace, type TraceNodeData } from "./agent-trace";

const CATEGORY_LABEL: Record<string, string> = {
  technical: "技术",
  behavioral: "行为",
  system_design: "系统设计",
};

const CATEGORY_COLOR: Record<string, string> = {
  technical: "text-indigo-600 dark:text-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/20 px-1.5 py-0.5 rounded text-[9px] font-bold",
  behavioral: "text-amber-600 dark:text-amber-400 bg-amber-50/50 dark:bg-amber-950/20 px-1.5 py-0.5 rounded text-[9px] font-bold",
  system_design: "text-violet-600 dark:text-violet-400 bg-violet-50/50 dark:bg-violet-950/20 px-1.5 py-0.5 rounded text-[9px] font-bold",
};

interface PreparationCardProps {
  status: "running" | "done" | "waiting_direction";
  nodes: TraceNodeData[];
  questions: PreparedQuestion[];
  summary: string;
  direction?: string;
  jdContext?: JDContext;
  onStart: () => void;
  started?: boolean;
}

export function PreparationCard({
  status,
  nodes,
  questions,
  summary,
  direction,
  jdContext,
  onStart,
  started = false,
}: PreparationCardProps) {
  const [expanded, setExpanded] = useState(status === "running");
  const [showQuestions, setShowQuestions] = useState(false);

  useEffect(() => {
    if (status === "running") {
      setExpanded(true);
    }
  }, [status]);

  const isDone = status === "done";
  const statusText = status === "running"
    ? "正在调度"
    : isDone
    ? "调度中心：准备就绪"
    : "等待方向";

  return (
    <div
      className={
        status === "running"
          ? "w-full mx-0 my-1 bg-transparent transition-all duration-300 animate-in fade-in slide-in-from-bottom-2 duration-300"
          : "w-full mx-0 my-0 bg-transparent transition-all duration-300"
      }
    >
      {/* 页眉工具栏：始终展示，作为 Master 的身份标识 */}
      <div className="pb-1 mb-2.5">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="inline-flex items-center gap-2 px-1 py-1 text-[10px] font-bold text-black/35 hover:text-[#534AB7] hover:underline dark:text-white/35 dark:hover:text-[#CECBF6] transition-all"
        >
          <span
            className={`size-1.5 rounded-full ${isDone ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.4)]" : "bg-[#534AB7] animate-pulse"}`}
          />
          <span>{statusText}</span>
          {direction && (
            <span className="text-[10px] font-bold text-[#534AB7] dark:text-[#CECBF6]">
              <span className="opacity-40 mr-0.5 select-none">#</span>
              <span>{direction}</span>
            </span>
          )}
          <span className="text-[9px] opacity-60 ml-1">
            ({expanded ? "收起专家组详情" : "展开专家组详情"})
          </span>
        </button>
      </div>

      {/* 展开态：包含完整的 Agent Trace */}
      {expanded && (
        <div className="bg-transparent transition-all duration-300 pt-1 pb-2">
          <AgentTrace nodes={nodes} />
        </div>
      )}

      {/* 结果呈现区：当 Done 时，以精致卡片形式展现，提升仪式感 */}
      {isDone && (
        <div className="mt-4 p-5 rounded-2xl border border-black/[0.03] bg-zinc-50/30 dark:bg-white/[0.02] dark:border-white/[0.05] shadow-sm animate-in fade-in slide-in-from-top-2 duration-700">
          {summary && (
            <p className="mb-5 text-[13px] font-bold leading-relaxed text-black/70 dark:text-white/80">
              {summary}
            </p>
          )}

          {jdContext && !expanded && (
            <div className="mb-5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-black/45 dark:text-white/40">
              <span className="font-bold text-black/60 dark:text-white/60">关联岗位:</span>
              {jdContext.company && <span>{jdContext.company}</span>}
              {jdContext.role && (
                <span className="text-[#534AB7] dark:text-[#CECBF6] font-medium">{jdContext.role}</span>
              )}
            </div>
          )}

          {/* 操作按钮区 */}
          <div className="flex flex-wrap items-center gap-4">
            {!started && (
              <button
                onClick={onStart}
                className="flex items-center justify-center gap-2 rounded-xl bg-[#534AB7] hover:bg-[#433A9F] px-5 py-2.5 text-xs font-black text-white shadow-md shadow-[#534AB7]/20 hover:shadow-lg hover:shadow-[#534AB7]/30 transition-all hover:scale-[1.02] active:scale-95 duration-200"
              >
                <span>▷</span> 开始本轮面试
              </button>
            )}
            <button
              onClick={() => setShowQuestions((v) => !v)}
              className="flex items-center justify-center gap-1.5 text-xs font-bold text-black/40 hover:text-[#534AB7] hover:underline active:scale-95 transition-all dark:text-white/40 dark:hover:text-[#CECBF6]"
            >
              <span>≡</span> {showQuestions ? "收起题目预览" : "全量题目预览"}
            </button>
          </div>

          {/* 题目列表预览容器 */}
          <div className={`grid transition-all duration-300 ease-in-out ${showQuestions ? "grid-rows-[1fr] opacity-100 mt-6 pt-2" : "grid-rows-[0fr] opacity-0"}`}>
            <div className="overflow-hidden">
              <div className="space-y-6 py-2 border-t border-black/[0.05] dark:border-white/[0.05]">
                {questions.length === 0 ? (
                  <div className="text-xs text-black/35 dark:text-white/30 text-center py-4">
                    题目生成中...
                  </div>
                ) : (
                  questions.map((q, i) => (
                    <div key={q.id || i} className="flex gap-4 py-0.5 items-start animate-in fade-in slide-in-from-left-2 duration-300">
                      <span className="w-6 flex-shrink-0 select-none font-mono text-[13px] font-bold text-[#534AB7] dark:text-[#CECBF6] leading-[1.65]">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-[13px] font-bold leading-[1.65] text-black/80 dark:text-white/90">
                          {q.question}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <span className="inline-flex items-center rounded bg-[#534AB7]/5 px-1 py-0.5 text-[9px] font-black text-[#534AB7]/60 dark:bg-[#CECBF6]/10 dark:text-[#CECBF6]/60 uppercase tracking-tighter">
                            {CATEGORY_LABEL[q.category] ?? q.category}
                          </span>
                          {q.focus_area && (
                            <span className="text-[9px] font-bold text-black/30 dark:text-white/25">
                              # {q.focus_area}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

