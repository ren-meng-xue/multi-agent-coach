"use client";

import { useState } from "react";

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

  return (
    <div className="border border-slate-100 rounded-xl mx-4 mt-3 bg-white shadow-sm overflow-hidden animate-in fade-in duration-300">
      {/* 头部状态条 */}
      <div className="flex items-center justify-between px-5 py-3 bg-slate-50/80 border-b border-slate-100/50">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full flex-shrink-0 transition-all duration-300 ${
              status === "done"
                ? "bg-emerald-500 shadow-sm shadow-emerald-300"
                : status === "running"
                ? "bg-indigo-500 animate-pulse"
                : "bg-slate-300"
            }`}
          />
          <span className="text-xs font-bold text-slate-800">
            {status === "running"
              ? "多 Agent 面试官就绪中..."
              : status === "done"
              ? "面试准备就绪"
              : "正在等待面试练习方向"}
          </span>
          {direction && (
            <span className="text-[10px] px-2 py-0.5 bg-indigo-600 text-white rounded-full font-bold shadow-sm animate-in zoom-in-75 duration-300">
              {direction}
            </span>
          )}
        </div>

        {status !== "running" && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="text-[10px] text-slate-400 hover:text-slate-600 hover:bg-slate-100/80 flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-all active:scale-95 font-semibold"
          >
            <span>就绪</span>
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
        <div className="max-h-72 overflow-y-auto bg-white/50 border-b border-slate-50 animate-in slide-in-from-top-2 duration-300">
          <AgentTrace nodes={nodes} />
        </div>
      )}

      {/* 收起态（或者是 done 状态下的摘要控制）：卡片大纲与 CTA 按钮 */}
      {status === "done" && !expanded && (
        <div className="px-5 py-4 bg-white animate-in fade-in duration-300">
          {summary && (
            <p className="text-xs text-slate-500 mb-3.5 leading-relaxed font-medium">
              {summary}
            </p>
          )}
          <div className="flex gap-2.5">
            <button
              onClick={onStart}
              className="flex items-center justify-center gap-1.5 px-5 py-2 bg-indigo-600 text-white rounded-full text-xs font-bold hover:bg-indigo-700 shadow-sm shadow-indigo-100 active:scale-95 transition-all"
            >
              <span>▷</span> 开始第 1 题
            </button>
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center justify-center gap-1.5 px-5 py-2 border border-slate-200 text-slate-600 rounded-full text-xs font-semibold hover:bg-slate-50 hover:border-slate-300 active:scale-95 transition-all"
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
