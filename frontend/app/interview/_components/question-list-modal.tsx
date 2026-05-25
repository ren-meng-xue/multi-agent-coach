"use client";

import type { PreparedQuestion } from "@/lib/prepare-types";

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

interface QuestionListModalProps {
  open: boolean;
  questions: PreparedQuestion[];
  onClose: () => void;
  onStart: () => void;
}

export function QuestionListModal({
  open,
  questions,
  onClose,
  onStart,
}: QuestionListModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 animate-in fade-in duration-200">
      {/* 背景遮罩 */}
      <div
        className="absolute inset-0 bg-slate-900/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 弹窗内容 */}
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden border border-slate-100 flex flex-col max-h-[85vh] animate-in slide-in-from-bottom-8 duration-300">
        {/* 头部 */}
        <div className="px-6 py-4.5 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-base font-bold text-slate-800 flex items-center gap-2">
            <span>≡</span> 专属面试考题
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 text-2xl leading-none w-8 h-8 rounded-full flex items-center justify-center hover:bg-slate-50 transition-colors"
          >
            ×
          </button>
        </div>

        {/* 题目列表 */}
        <div className="px-6 py-3 overflow-y-auto divide-y divide-slate-100 flex-1">
          {questions.map((q, i) => (
            <div key={q.id || i} className="py-4 flex gap-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
              <span className="text-sm font-black text-slate-200 font-mono w-5 pt-0.5 select-none">
                {(i + 1).toString().padStart(2, "0")}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-800 leading-relaxed font-semibold">
                  {q.question}
                </p>
                <div className="flex gap-2.5 mt-2 flex-wrap items-center">
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded border font-bold shadow-sm ${
                      CATEGORY_COLOR[q.category] ||
                      "bg-slate-50 text-slate-600 border-slate-200"
                    }`}
                  >
                    {CATEGORY_LABEL[q.category] || q.category}
                  </span>
                  {q.focus_area && (
                    <span className="text-[10px] text-slate-400 font-medium">
                      考点：{q.focus_area}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* 底部 CTA 区域 */}
        <div className="px-6 py-4.5 border-t border-slate-100 bg-slate-50/50 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 px-4 rounded-xl border border-slate-200 text-slate-600 text-sm font-semibold hover:bg-slate-100 hover:border-slate-300 transition-all active:scale-[0.98]"
          >
            取消
          </button>
          <button
            onClick={onStart}
            className="flex-[2] py-2.5 px-4 bg-indigo-600 text-white rounded-xl text-sm font-bold shadow-md shadow-indigo-100 hover:bg-indigo-700 hover:shadow-indigo-200 transition-all active:scale-[0.98]"
          >
            开始第1题
          </button>
        </div>
      </div>
    </div>
  );
}
