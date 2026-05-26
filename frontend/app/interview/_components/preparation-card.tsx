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
  technical: "bg-indigo-50 text-indigo-700 border-indigo-100",
  behavioral: "bg-amber-50 text-amber-700 border-amber-100",
  system_design: "bg-violet-50 text-violet-700 border-violet-100",
};

interface PreparationCardProps {
  status: "running" | "done" | "waiting_direction";
  nodes: TraceNodeData[];
  questions: PreparedQuestion[];
  summary: string;
  direction?: string;
  jdContext?: JDContext;
  onStart: () => void;
}

export function PreparationCard({
  status,
  nodes,
  questions,
  summary,
  direction,
  jdContext,
  onStart,
}: PreparationCardProps) {
  const [expanded, setExpanded] = useState(status === "running");
  const [showQuestions, setShowQuestions] = useState(false);

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
    <div className="mx-0 mt-3 overflow-hidden rounded-2xl border border-black/[0.04] bg-[#faf9f6]/95 backdrop-blur-md shadow-[0_8px_32px_rgba(0,0,0,0.02)] dark:border-white/[0.04] dark:bg-[#181817]/95 animate-in fade-in slide-in-from-top-4 duration-500">
      <div className="flex items-center justify-between border-b border-black/[0.04] dark:border-white/[0.04] bg-black/[0.01] dark:bg-white/[0.01] px-5 py-3.5">
        <div className="flex items-center gap-2">
          <span
            className={`size-2 rounded-full flex-shrink-0 transition-all duration-500 ${
              isDone
                ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]"
                : status === "running"
                ? "bg-[#534AB7] dark:bg-[#CECBF6] animate-pulse shadow-[0_0_8px_rgba(83,74,183,0.4)]"
                : "bg-black/20 dark:bg-white/20"
            }`}
          />
          <span className="text-xs font-black tracking-wide text-black/80 dark:text-white/80">
            {statusText}
          </span>
          {direction && (
            <span className="rounded-full bg-[#EEEDFE] px-2.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wide text-[#3C3489] animate-in zoom-in-75 duration-300 dark:bg-[#26215C] dark:text-[#CECBF6]">
              {direction}
            </span>
          )}
        </div>

        {status !== "running" && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[10px] font-bold text-black/45 hover:bg-black/[0.03] hover:text-black/70 transition-all active:scale-95 dark:text-white/45 dark:hover:bg-white/[0.03] dark:hover:text-white/70"
          >
            <span>{isDone ? "就绪" : "查看"}</span>
            <span
              className={`transform transition-transform duration-300 font-mono text-[8px] ${
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
        <div className="max-h-80 overflow-y-auto border-b border-black/[0.03] dark:border-white/[0.03] bg-transparent animate-in slide-in-from-top-2 duration-300">
          <AgentTrace nodes={nodes} />
        </div>
      )}

      {status === "done" && !expanded && (
        <div className="px-5 py-4 animate-in fade-in duration-500">
          {summary && (
            <p className="mb-4 text-xs font-semibold leading-relaxed text-black/60 dark:text-white/60">
              {summary}
            </p>
          )}

          {jdContext && (
            <div className="mb-5 border-t border-black/[0.04] pt-4 text-xs text-black/75 dark:border-white/[0.04] dark:text-white/75 animate-in fade-in slide-in-from-bottom-2 duration-500">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-3">
                {jdContext.company && (
                  <span className="flex items-center gap-1 font-extrabold text-black/85 dark:text-white/85">
                    🏢 <span className="font-semibold">{jdContext.company}</span>
                  </span>
                )}
                {jdContext.role && (
                  <span className="flex items-center gap-1 font-extrabold text-[#534AB7] dark:text-[#CECBF6]">
                    🎯 <span className="font-semibold">{jdContext.role}</span>
                  </span>
                )}
                {jdContext.difficulty && (
                  <span className="rounded bg-black/[0.04] dark:bg-white/[0.04] px-1.5 py-0.5 text-[9px] font-black tracking-wider uppercase text-black/40 dark:text-white/40">
                    ⚡ {jdContext.difficulty}
                  </span>
                )}
              </div>
              
              {jdContext.key_skills && jdContext.key_skills.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 mt-2">
                  <span className="text-[10px] font-bold text-black/35 dark:text-white/35 mr-1.5">核心要点:</span>
                  {jdContext.key_skills.map((skill, i) => (
                    <span
                      key={i}
                      className="rounded-lg bg-[#EEEDFE] px-2.5 py-0.5 text-[9px] font-extrabold text-[#3C3489] transition-all hover:scale-105 dark:bg-[#26215C] dark:text-[#CECBF6]"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-2.5">
            <button
              onClick={onStart}
              className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#534AB7] to-[#7164E4] px-5 py-2.5 text-xs font-bold text-white shadow-[0_4px_16px_rgba(83,74,183,0.15)] hover:shadow-[0_6px_20px_rgba(83,74,183,0.25)] transition-all hover:scale-[1.02] active:scale-95 duration-200"
            >
              <span>▷</span> 开始第 1 题
            </button>
            <button
              onClick={() => setShowQuestions((v) => !v)}
              className="flex items-center justify-center gap-1.5 rounded-xl border border-black/[0.08] px-4 py-2 text-xs font-bold text-black/60 hover:bg-black/[0.02] active:scale-95 transition-all dark:border-white/10 dark:text-white/60 dark:hover:bg-white/[0.02]"
            >
              <span>≡</span> {showQuestions ? "收起题目" : "先看题目列表"}
            </button>
          </div>

          {/* 纯 CSS Grid 实现的高度自适应平滑动画折叠容器，消除瞬间卡顿感 */}
          <div className={`grid transition-all duration-300 ease-in-out ${showQuestions ? "grid-rows-[1fr] opacity-100 mt-4 border-t border-black/[0.04] dark:border-white/[0.04] pt-2" : "grid-rows-[0fr] opacity-0"}`}>
            <div className="overflow-hidden">
              <div className="divide-y divide-black/[0.03] dark:divide-white/[0.03]">
                {questions.length === 0 ? (
                  <p className="py-4 text-xs text-black/35 dark:text-white/35">题目生成中，请稍候…</p>
                ) : (
                  questions.map((q, i) => (
                    <div key={q.id || i} className="flex gap-4.5 py-3.5">
                      <span className="w-5 select-none pt-0.5 font-mono text-[10px] font-black text-black/15 dark:text-white/15">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-bold leading-relaxed text-black/85 dark:text-white/85">
                          {q.question}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2.5">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[9px] font-black tracking-widest ${
                              CATEGORY_COLOR[q.category] ?? "border border-black/10 bg-black/[0.02] text-black/55"
                            }`}
                          >
                            {CATEGORY_LABEL[q.category] ?? q.category}
                          </span>
                          {q.focus_area && (
                            <span className="text-[9px] font-semibold text-black/30 dark:text-white/30">
                              考点：{q.focus_area}
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
