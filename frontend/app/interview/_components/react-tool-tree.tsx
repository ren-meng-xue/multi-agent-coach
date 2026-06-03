import type { ReactIteration } from "@/lib/prepare-types";
import { Loader2, Wrench, AlertCircle, CheckCircle2, ChevronRight } from "lucide-react";

export function ReactToolTree({
  steps,
  isFinished,
}: {
  steps: ReactIteration[];
  isFinished?: boolean;
}) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 mt-2" data-testid="react-tool-tree">
      {steps.map((step) => (
        <details
          key={step.index}
          className="group rounded-md border border-black/10 bg-black/5 p-2 dark:border-white/10 dark:bg-white/5"
          open={!isFinished && step.index === steps.length - 1} // 最后一个正在运行的默认打开
        >
          <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium text-black/80 dark:text-white/80 list-none [&::-webkit-details-marker]:hidden">
            <ChevronRight className="h-4 w-4 transition-transform group-open:rotate-90" />
            <span className="flex-1">🤔 第 {step.index + 1} 步思考与执行</span>
            {step.thinkStatus === "running" && <Loader2 className="h-3 w-3 animate-spin text-blue-500" data-testid="think-spinner" />}
          </summary>
          <div className="mt-2 flex flex-col gap-3 pl-6 border-l-2 border-black/10 dark:border-white/10 text-sm">
            {step.thinkContent && (
              <div className="whitespace-pre-wrap text-black/70 dark:text-white/70">
                {step.thinkContent}
              </div>
            )}
            
            {step.toolCalls.length > 0 && (
              <div className="flex flex-col gap-2">
                {step.toolCalls.map((tc) => (
                  <div key={tc.stepId} className="rounded border border-black/10 bg-white dark:border-white/10 dark:bg-black/20 p-2" data-testid={`tool-call-${tc.toolName}`}>
                    <div className="flex items-center gap-2 font-mono text-xs text-black/80 dark:text-white/80 mb-1">
                      <Wrench className="h-3 w-3" />
                      <span className="font-semibold">{tc.toolName}</span>
                      {tc.status === "running" && <Loader2 className="h-3 w-3 animate-spin text-blue-500 ml-auto" data-testid="tool-spinner" />}
                      {tc.status === "done" && <span className="text-green-600 dark:text-green-400 ml-auto flex items-center gap-1"><CheckCircle2 className="h-3 w-3" /> {tc.elapsedMs}ms</span>}
                      {tc.status === "error" && <span className="text-red-600 dark:text-red-400 ml-auto flex items-center gap-1"><AlertCircle className="h-3 w-3" /> {tc.elapsedMs}ms</span>}
                    </div>
                    {tc.argsSummary && (
                      <div className="text-xs text-black/60 dark:text-white/60 font-mono bg-black/5 dark:bg-white/5 p-1 rounded">
                        {tc.argsSummary}
                      </div>
                    )}
                    {tc.resultSummary && (
                      <div className="text-xs text-black/70 dark:text-white/70 font-mono mt-1 whitespace-pre-wrap border-t border-black/5 dark:border-white/5 pt-1">
                        {tc.resultSummary}
                      </div>
                    )}
                    {tc.error && (
                      <div className="text-xs text-red-600 dark:text-red-400 font-mono mt-1 whitespace-pre-wrap border-t border-black/5 dark:border-white/5 pt-1">
                        {tc.error}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}