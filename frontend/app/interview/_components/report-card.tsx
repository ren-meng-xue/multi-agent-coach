import type { InterviewReport } from "@/lib/interview-chat";

const DIMENSION_LABELS: Record<
  "technical_depth" | "quantified_results" | "failure_tradeoffs" | "structure",
  string
> = {
  technical_depth: "技术深度",
  quantified_results: "量化结果",
  failure_tradeoffs: "失败与权衡",
  structure: "结构完整性",
};

const DIMENSIONS = Object.keys(DIMENSION_LABELS) as Array<keyof typeof DIMENSION_LABELS>;

function ScoreBar({ score }: { score: number }) {
  const percent = Math.round((Math.min(Math.max(score, 0), 5) / 5) * 100);
  return (
    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
      <div
        className="h-full rounded-full bg-[#534AB7] transition-[width] duration-500"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

export function ReportCard({ report }: { report: InterviewReport }) {
  return (
    <div className="mx-auto w-full max-w-xl rounded-xl border border-black/10 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1c1c1a]">
      <h2 className="mb-1 text-sm font-bold text-black/80 dark:text-white/80">本轮面试报告</h2>
      <div className="mb-4 flex items-baseline gap-1.5">
        <span className="bg-gradient-to-br from-[#534AB7] to-rose-600 bg-clip-text text-3xl font-bold text-transparent">
          {report.overall_score.toFixed(1)}
        </span>
        <span className="text-sm text-black/45 dark:text-white/45">/ 10</span>
      </div>

      <div className="mb-4 space-y-2.5">
        {DIMENSIONS.map((key) => (
          <div key={key} className="flex items-center gap-3">
            <span className="w-20 shrink-0 text-xs text-black/55 dark:text-white/55">
              {DIMENSION_LABELS[key]}
            </span>
            <ScoreBar score={report[key]} />
            <span className="w-12 shrink-0 text-right text-xs font-medium text-black/70 dark:text-white/70">{report[key].toFixed(1)} / 5</span>
          </div>
        ))}
      </div>

      {report.highlights.length > 0 && (
        <div className="mb-3">
          <p className="mb-1.5 text-xs font-semibold text-black/60 dark:text-white/60">亮点</p>
          <ul className="space-y-1">
            {report.highlights.map((item, i) => (
              <li key={i} className="flex gap-1.5 text-xs text-black/70 dark:text-white/70">
                <span className="mt-0.5 shrink-0 text-[#534AB7]">·</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.improvements.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-semibold text-black/60 dark:text-white/60">改进建议</p>
          <ul className="space-y-1">
            {report.improvements.map((item, i) => (
              <li key={i} className="flex gap-1.5 text-xs text-black/70 dark:text-white/70">
                <span className="mt-0.5 shrink-0 text-rose-500">·</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
