"use client";

import { useEffect, useState } from "react";

import type { PreparedQuestion } from "@/lib/prepare-types";
import { AgentTrace, type TraceNodeData } from "./agent-trace";
import { QuestionListModal } from "./question-list-modal";

interface PreparationCardProps {
  status: "running" | "done" | "waiting_direction";
  nodes: TraceNodeData[];
  questions: PreparedQuestion[];
  summary: string;
  direction?: string;
  onStart: () => void;
}

export function PreparationCard({
  status,
  nodes,
  questions,
  summary,
  direction,
  onStart,
}: PreparationCardProps) {
  const [expanded, setExpanded] = useState(status === "running");
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    if (status === "running") {
      setExpanded(true);
      return;
    }
    if (status === "done") {
      setExpanded(false);
    }
  }, [status]);

  const isDone = status === "done";
  const statusText = status === "running"
    ? "专家组正在工作"
    : isDone
    ? "准备完成"
    : "等待方向";

  return (
    <div className="mx-0 mt-1 overflow-hidden rounded-xl border border-black/10 bg-white shadow-sm animate-in fade-in duration-300 dark:border-white/10 dark:bg-[#1c1c1a]">
      <div className="flex items-center justify-between border-b border-black/10 bg-[#f7f6f2] px-4 py-3 dark:border-white/10 dark:bg-[#252523]">
        <div className="flex items-center gap-2">
          <span
            className={`size-2 rounded-full flex-shrink-0 transition-all duration-300 ${
              isDone
                ? "bg-[#1D9E75]"
                : status === "running"
                ? "bg-[#534AB7] animate-pulse shadow-[0_0_0_4px_rgba(83,74,183,0.12)]"
                : "bg-black/25 dark:bg-white/25"
            }`}
          />
          <span className="text-xs font-bold text-[#1a1a18] dark:text-[#e8e6de]">
            {statusText}
          </span>
          {direction && (
            <span className="rounded-full bg-[#EEEDFE] px-2 py-0.5 text-[10px] font-bold text-[#3C3489] animate-in zoom-in-75 duration-300 dark:bg-[#26215C] dark:text-[#CECBF6]">
              {direction}
            </span>
          )}
        </div>

        {status !== "running" && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[10px] font-semibold text-black/40 transition-all hover:bg-black/5 hover:text-black/65 active:scale-95 dark:text-white/40 dark:hover:bg-white/5 dark:hover:text-white/65"
          >
            <span>{isDone ? "就绪" : "查看"}</span>
            <span
              className={`transform transition-transform duration-300 font-mono text-[9px] ${
                expanded ? "rotate-180" : ""
              }`}
            >
              ▼
            </span>
          </button>
        )}
      </div>

      {/* 展开态：完整 Trace 运行过程（running 时强制展开，done 时受 expanded 控制） */}
      {(status === "running" || expanded) && (
        <div className="max-h-72 overflow-y-auto border-b border-black/5 bg-white animate-in slide-in-from-top-2 duration-300 dark:border-white/10 dark:bg-[#1c1c1a]">
          <AgentTrace nodes={nodes} />
        </div>
      )}

      {status === "done" && !expanded && (
        <div className="bg-white px-4 py-3 animate-in fade-in duration-300 dark:bg-[#1c1c1a]">
          {summary && (
            <p className="mb-3 text-xs font-medium leading-relaxed text-black/55 dark:text-white/55">
              {summary}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={onStart}
              className="flex items-center justify-center gap-1.5 rounded-lg bg-[#534AB7] px-4 py-2 text-xs font-bold text-white shadow-sm shadow-[#534AB7]/15 transition-all hover:bg-[#463da3] active:scale-95"
            >
              <span>▷</span> 开始第 1 题
            </button>
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center justify-center gap-1.5 rounded-lg border border-black/10 px-4 py-2 text-xs font-semibold text-black/60 transition-all hover:border-black/20 hover:bg-black/[0.03] active:scale-95 dark:border-white/10 dark:text-white/60 dark:hover:border-white/20 dark:hover:bg-white/[0.04]"
            >
              <span>≡</span> 先看题目列表
            </button>
          </div>
        </div>
      )}

      <QuestionListModal
        open={showModal}
        questions={questions}
        onClose={() => setShowModal(false)}
        onStart={() => {
          setShowModal(false);
          onStart();
        }}
      />
    </div>
  );
}
