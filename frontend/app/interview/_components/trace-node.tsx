"use client";

export type TraceNodeStatus = "pending" | "running" | "done";

interface TraceNodeProps {
  id: string;
  label: string;
  title: string;
  status: TraceNodeStatus;
  tokens: string; // 流式积累的文本（LLM 逐字输出，非固定文案）
  elapsedMs?: number;
}

export function TraceNode({
  id,
  label,
  title,
  status,
  tokens,
  elapsedMs,
}: TraceNodeProps) {
  return (
    <div data-testid={`trace-node-${id}`} className="flex gap-4 py-2.5 group">
      {/* 左侧状态圆圈与垂直连接线 */}
      <div className="flex flex-col items-center gap-1 pt-1">
        {status === "pending" && (
          <div
            data-testid="trace-status-pending"
            className="w-6 h-6 rounded-full border-2 border-slate-200 bg-slate-50/50 flex-shrink-0 transition-colors duration-300"
          />
        )}
        {status === "running" && (
          <div
            data-testid="trace-status-running"
            className="w-6 h-6 rounded-full border-2 border-indigo-500 border-t-transparent flex-shrink-0 animate-spin"
          />
        )}
        {status === "done" && (
          <div
            data-testid="trace-status-done"
            className="w-6 h-6 rounded-full bg-emerald-500 text-white flex-shrink-0 flex items-center justify-center shadow-sm shadow-emerald-200 animate-in fade-in zoom-in-50 duration-300"
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={3}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
        )}
        {/* 竖线连接下一个节点 */}
        <div className="w-0.5 flex-1 bg-slate-100 group-last:bg-transparent mt-1 min-h-[16px]" />
      </div>

      {/* 右侧内容区 */}
      <div className="flex-1 pb-4 min-w-0">
        <div className="flex items-center gap-2.5 mb-1.5 flex-wrap">
          <span className="text-[10px] uppercase tracking-wider font-extrabold px-2 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-100 shadow-sm">
            {label}
          </span>
          <span className="text-xs font-semibold text-slate-800">{title}</span>
          {status === "running" && (
            <span className="flex gap-0.5 text-indigo-500 font-bold text-[10px] animate-pulse">
              <span>●</span>
              <span>●</span>
              <span>●</span>
            </span>
          )}
          {elapsedMs !== undefined && (
            <span className="ml-auto text-[10px] font-mono text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100/50">
              {elapsedMs}ms
            </span>
          )}
        </div>

        {/* 流式 token 文本（逐字渲染，非固定文案） */}
        {tokens && (
          <div className="text-xs text-slate-600 leading-relaxed font-normal whitespace-pre-wrap pl-1.5 space-y-1 animate-in fade-in slide-in-from-top-1 duration-300">
            {tokens.split("\n").map((line, i) => {
              const trimmed = line.trim();
              if (!trimmed) return null;
              return (
                <div key={i} className="flex gap-2 mt-1">
                  <span className="text-slate-300 flex-shrink-0 select-none">•</span>
                  <span className="text-slate-600 font-normal">
                    {trimmed.replace(/^[•\-]\s*/, "")}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
