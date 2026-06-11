import type { Metadata } from "next";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  FileWarning,
  FlaskConical,
  Gauge,
  GitBranch,
  TimerReset,
  XCircle,
} from "lucide-react";
import { AppShell } from "../components/app-shell";

export const metadata: Metadata = {
  title: "AI 面试官测试报告 - Multi Agent Coach",
  description: "AI 面试官 Agent 维度一功能验证可视化报告",
};

type Status = "passed" | "failed" | "blocked" | "pending";

type TestCase = {
  id: string;
  title: string;
  priority: "高" | "中";
  weight: 5 | 3;
  status: Status;
  measured: string;
  evidence: string;
};

type Section = {
  code: string;
  title: string;
  color: string;
  targetScore: number;
  cases: TestCase[];
};

const sections: Section[] = [
  {
    code: "F1",
    title: "启动与初始化",
    color: "#4f46e5",
    targetScore: 18,
    cases: [
      {
        id: "F1-1",
        title: "Prepare -> Interview 状态流转正确触发",
        priority: "高",
        weight: 5,
        status: "passed",
        measured: "prepare done 后发 launch、phase_change、turn_done",
        evidence: "backend tests/unit/test_prepare_launch.py 覆盖事件顺序",
      },
      {
        id: "F1-2",
        title: "开场白包含 JD 岗位名称且无占位符",
        priority: "高",
        weight: 5,
        status: "passed",
        measured: "首题开场使用 target_role 生成岗位引导",
        evidence: "backend tests/unit/test_prepare_interview_integration.py 覆盖岗位名注入；当前用户模型无姓名字段",
      },
      {
        id: "F1-3",
        title: "面试上下文正确注入 JD、简历摘要、题库",
        priority: "高",
        weight: 5,
        status: "passed",
        measured: "prepared_questions、jd_context、job_intel 均进入 turn state",
        evidence: "backend integration tests 覆盖准备题、JD 上下文和岗位情报注入",
      },
      {
        id: "F1-4",
        title: "重复启动同一 session 不创建两个面试实例",
        priority: "中",
        weight: 3,
        status: "passed",
        measured: "同一用户复用 in_progress session",
        evidence: "backend tests/integration/test_interview_turn_service.py 覆盖 active run 复用",
      },
    ],
  },
  {
    code: "F2",
    title: "多轮对话流程",
    color: "#059669",
    targetScore: 18,
    cases: [
      {
        id: "F2-1",
        title: "完整跑通 5 轮问答后面试官主动结束",
        priority: "高",
        weight: 5,
        status: "passed",
        measured: "第 5 题 closing 后 session.status=completed",
        evidence: "backend tests/integration/test_interview_turn_service.py 覆盖 closing/report/session",
      },
      {
        id: "F2-2",
        title: "对话历史在轮次间正确保留",
        priority: "高",
        weight: 5,
        status: "passed",
        measured: "后续 turn state 含前轮 user/assistant 历史",
        evidence: "backend tests/integration/test_interview_turn_service.py 覆盖跨轮历史加载",
      },
      {
        id: "F2-3",
        title: "SSE/WebSocket 流式输出不中断",
        priority: "高",
        weight: 5,
        status: "passed",
        measured: "SSE delta/state/report/done/error 序列均有自动化覆盖",
        evidence: "backend route/service tests + frontend stream parser tests 覆盖",
      },
      {
        id: "F2-4",
        title: "候选人发送空消息时面试官正确处理",
        priority: "中",
        weight: 3,
        status: "passed",
        measured: "SSE 返回礼貌引导，未进入 LangGraph",
        evidence: "backend tests/unit/test_interview_routes.py 覆盖空消息 delta/done",
      },
    ],
  },
  {
    code: "F3",
    title: "工具调用链",
    color: "#7c3aed",
    targetScore: 18,
    cases: [
      {
        id: "F3-1",
        title: "准备题库被 Designer 正确消费",
        priority: "高",
        weight: 5,
        status: "passed",
        measured: "Designer 优先使用 prepared_questions，避免 LLM 新题覆盖",
        evidence: "backend tests/unit/test_designer_agent.py 覆盖 prepared source 与 dual new_question_source",
      },
      {
        id: "F3-2",
        title: "追问时不重复调用题库",
        priority: "中",
        weight: 3,
        status: "passed",
        measured: "准备题优先使用，追问卡片不触发额外题库查询",
        evidence: "designer/prepare integration tests + frontend HeroQuestionCard test 覆盖",
      },
      {
        id: "F3-3",
        title: "Evaluate 工具在面试流程中正确触发并汇总",
        priority: "高",
        weight: 5,
        status: "passed",
        measured: "Chief 每轮调用 evaluate_answer，closing 时 report 聚合 turn_evaluations",
        evidence: "backend tests/unit/test_chief_reasoning.py + test_interview_turn_service.py 覆盖评估调用与 report/session completed",
      },
      {
        id: "F3-4",
        title: "工具调用失败时面试官降级处理",
        priority: "高",
        weight: 5,
        status: "passed",
        measured: "Evaluator/Designer 异常写入错误标记且不崩溃",
        evidence: "backend tests/unit/test_chief_safety.py 覆盖工具异常恢复",
      },
    ],
  },
  {
    code: "F4",
    title: "异常场景",
    color: "#d97706",
    targetScore: 19,
    cases: [
      {
        id: "F4-1",
        title: "候选人 3 分钟无响应",
        priority: "高",
        weight: 5,
        status: "blocked",
        measured: "当前系统没有候选人无响应计时/挂起机制",
        evidence: "需要新增前端计时器或后端 session watcher 后才能测试",
      },
      {
        id: "F4-2",
        title: "候选人答案完全离题",
        priority: "高",
        weight: 5,
        status: "passed",
        measured: "chain=['followup'] 时拉回主题且不触发 evaluator",
        evidence: "backend tests/unit/test_prepare_interview_integration.py 覆盖跑题拉回",
      },
      {
        id: "F4-3",
        title: "候选人要求跳过问题",
        priority: "中",
        weight: 3,
        status: "passed",
        measured: "识别跳过意图后跳过评估，直接设计下一题",
        evidence: "backend tests/unit/test_chief_reasoning.py 覆盖跳过请求进入下一题",
      },
      {
        id: "F4-4",
        title: "候选人提交超长回答（>1000 字）",
        priority: "中",
        weight: 3,
        status: "passed",
        measured: ">1000 字回答完整进入图状态并持久化",
        evidence: "backend tests/integration/test_interview_turn_service.py 覆盖长文本",
      },
      {
        id: "F4-5",
        title: "LLM API 超时或返回错误",
        priority: "高",
        weight: 5,
        status: "passed",
        measured: "后端返回 SSE error，前端展示明确错误",
        evidence: "backend route tests + frontend interview-chat error test 覆盖",
      },
    ],
  },
];

const automationRun = {
  command: "uv run pytest tests/ + pnpm test",
  startedAt: "2026-06-05 11:18:00",
  duration: "待复测",
  testFiles: { passed: 2, failed: 0, total: 2 },
  tests: { passed: 479, failed: 0, total: 479 },
  failures: [],
};

const statusMeta: Record<Status, { label: string; className: string }> = {
  passed: {
    label: "通过",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  failed: {
    label: "失败",
    className: "border-rose-200 bg-rose-50 text-rose-700",
  },
  blocked: {
    label: "阻塞",
    className: "border-amber-200 bg-amber-50 text-amber-700",
  },
  pending: {
    label: "待执行",
    className: "border-slate-200 bg-slate-50 text-slate-600",
  },
};

const allCases = sections.flatMap((section) => section.cases);
const maxScore = sections.reduce((sum, section) => sum + section.targetScore, 0);
const currentScore = allCases.reduce((sum, item) => {
  if (item.status === "passed") return sum + item.weight;
  return sum;
}, 0);
const highPriority = allCases.filter((item) => item.priority === "高");
const highPriorityPassed = highPriority.filter((item) => item.status === "passed");
const failedCases = allCases.filter((item) => item.status === "failed");
const pendingCases = allCases.filter((item) => item.status === "pending");
const blockedCases = allCases.filter((item) => item.status === "blocked");
const scorePercent = Math.round((currentScore / maxScore) * 100);
const automationPassRate = Math.round(
  (automationRun.tests.passed / automationRun.tests.total) * 100,
);
const admissionPassed =
  currentScore >= 66 &&
  highPriorityPassed.length === highPriority.length &&
  failedCases.length === 0 &&
  blockedCases.length === 0;
const admissionLabel = admissionPassed
  ? "通过"
  : blockedCases.length > 0
    ? "阻塞"
    : "有条件通过";
const admissionClassName = admissionPassed
  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
  : blockedCases.length > 0
    ? "border-amber-200 bg-amber-50 text-amber-700"
    : "border-sky-200 bg-sky-50 text-sky-700";

function getSectionScore(section: Section) {
  const scored = section.cases.reduce(
    (sum, item) => sum + (item.status === "passed" ? item.weight : 0),
    0,
  );
  return {
    total: section.targetScore,
    scored,
    percent: Math.round((scored / section.targetScore) * 100),
  };
}

function StatusIcon({ status }: { status: Status }) {
  if (status === "passed") return <CheckCircle2 className="size-4" />;
  if (status === "failed") return <XCircle className="size-4" />;
  if (status === "blocked") return <AlertTriangle className="size-4" />;
  return <TimerReset className="size-4" />;
}

function MetricCard({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[#e8e7e2] bg-white p-4 shadow-sm">
      <div className="mb-5 flex items-center justify-between">
        <span className="text-xs font-bold uppercase text-[#8a8a8a]">{label}</span>
        <span className="flex size-8 items-center justify-center rounded-md bg-[#f5f4f0] text-[#171717]">
          {icon}
        </span>
      </div>
      <div className="text-3xl font-bold tracking-normal text-[#171717]">{value}</div>
      <p className="mt-1 text-sm text-[#525252]">{detail}</p>
    </div>
  );
}

function ScoreRing() {
  const radius = 78;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (scorePercent / 100) * circumference;

  return (
    <svg viewBox="0 0 200 200" className="h-[220px] w-[220px]" aria-label="总评分环图">
      <circle
        cx="100"
        cy="100"
        r={radius}
        fill="none"
        stroke="#e8e7e2"
        strokeWidth="18"
      />
      <circle
        cx="100"
        cy="100"
        r={radius}
        fill="none"
        stroke="#e11d48"
        strokeLinecap="round"
        strokeWidth="18"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform="rotate(-90 100 100)"
      />
      <text x="100" y="92" textAnchor="middle" className="fill-[#171717] text-[34px] font-bold">
        {currentScore}
      </text>
      <text x="100" y="118" textAnchor="middle" className="fill-[#8a8a8a] text-[13px] font-semibold">
        / {maxScore} 分
      </text>
    </svg>
  );
}

export default function TestReportPage() {
  return (
    <AppShell>
      <div className="mx-auto w-full max-w-[1280px] space-y-6 pb-8">
        <section className="grid gap-5 rounded-lg border border-[#e8e7e2] bg-white p-5 shadow-sm lg:grid-cols-[1.4fr_0.8fr]">
          <div>
            <div className={`mb-4 inline-flex items-center gap-2 rounded-md border px-3 py-1 text-xs font-bold ${admissionClassName}`}>
              {admissionPassed ? <CheckCircle2 className="size-3.5" /> : <FileWarning className="size-3.5" />}
              准入结论：{admissionLabel}
            </div>
            <h1 className="text-3xl font-bold tracking-normal text-[#171717]">
              AI 面试官 Agent 维度一测试报告
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[#525252]">
              依据 2026-06-05 维度一功能验证模板整理。本次已执行前后端自动化测试，F1-F4
              已将现有自动化证据映射到当前架构；剩余阻塞项为候选人无响应计时与自动挂起机制。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <div className="rounded-md bg-[#f5f4f0] p-3">
                <div className="text-xs font-bold text-[#8a8a8a]">报告日期</div>
                <div className="mt-1 text-sm font-semibold text-[#171717]">2026-06-05</div>
              </div>
              <div className="rounded-md bg-[#f5f4f0] p-3">
                <div className="text-xs font-bold text-[#8a8a8a]">范围</div>
                <div className="mt-1 text-sm font-semibold text-[#171717]">Prepare -&gt; Interview</div>
              </div>
              <div className="rounded-md bg-[#f5f4f0] p-3">
                <div className="text-xs font-bold text-[#8a8a8a]">执行命令</div>
                <div className="mt-1 text-sm font-semibold text-[#171717]">{automationRun.command}</div>
              </div>
            </div>
          </div>
          <div className="flex flex-col items-center justify-center rounded-lg border border-[#e8e7e2] bg-[#fafaf7] p-5">
            <ScoreRing />
            <div className="text-center">
              <div className="text-sm font-bold text-[#171717]">维度一功能准入评分</div>
              <p className="mt-1 text-xs text-[#8a8a8a]">目标：&gt;= 66 分且高优先级 100% 通过</p>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="自动化通过率"
            value={`${automationPassRate}%`}
            detail={`${automationRun.tests.passed}/${automationRun.tests.total} 个测试通过`}
            icon={<Gauge className="size-4" />}
          />
          <MetricCard
            label="失败用例"
            value={`${failedCases.length + automationRun.tests.failed}`}
            detail={`维度映射 ${failedCases.length} 项，自动化 ${automationRun.tests.failed} 项`}
            icon={<CheckCircle2 className="size-4" />}
          />
          <MetricCard
            label="待全链路执行"
            value={`${pendingCases.length + blockedCases.length}`}
            detail={`待执行 ${pendingCases.length} 项，阻塞 ${blockedCases.length} 项`}
            icon={<ClipboardCheck className="size-4" />}
          />
          <MetricCard
            label="高优先级覆盖"
            value={`${highPriorityPassed.length}/${highPriority.length}`}
            detail={blockedCases.length > 0 ? "仍有高优先级阻塞项" : "高优先级自动化覆盖已达标"}
            icon={<AlertTriangle className="size-4" />}
          />
        </section>

        <section className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-lg border border-[#e8e7e2] bg-white p-5 shadow-sm">
            <div className="mb-5 flex items-center gap-2">
              <FlaskConical className="size-5 text-[#4f46e5]" />
              <h2 className="text-lg font-bold text-[#171717]">本次自动化执行</h2>
            </div>
            <div className="space-y-4">
              <div>
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="font-semibold text-[#171717]">测试通过</span>
                  <span className="font-bold text-[#059669]">
                    {automationRun.tests.passed}/{automationRun.tests.total}
                  </span>
                </div>
                <div className="h-3 overflow-hidden rounded-full bg-[#f3f2ee]">
                  <div
                    className="h-full rounded-full bg-[#059669]"
                    style={{ width: `${automationPassRate}%` }}
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-md bg-[#f5f4f0] p-3">
                  <div className="text-xs text-[#8a8a8a]">测试套件</div>
                  <div className="mt-1 text-lg font-bold text-[#171717]">
                    {automationRun.testFiles.passed}/{automationRun.testFiles.total}
                  </div>
                </div>
                <div className="rounded-md bg-[#f5f4f0] p-3">
                  <div className="text-xs text-[#8a8a8a]">耗时</div>
                  <div className="mt-1 text-lg font-bold text-[#171717]">{automationRun.duration}</div>
                </div>
                <div className="rounded-md bg-[#f5f4f0] p-3">
                  <div className="text-xs text-[#8a8a8a]">开始</div>
                  <div className="mt-1 text-sm font-bold text-[#171717]">10:53:28</div>
                </div>
              </div>
              <div className="space-y-2">
                {automationRun.failures.length > 0 ? (
                  automationRun.failures.map((failure) => (
                    <div
                      className="flex gap-2 rounded-md border border-rose-100 bg-rose-50 px-3 py-2 text-sm text-rose-800"
                      key={failure}
                    >
                      <XCircle className="mt-0.5 size-4 flex-shrink-0" />
                      <span>{failure}</span>
                    </div>
                  ))
                ) : (
                  <div className="flex gap-2 rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                    <CheckCircle2 className="mt-0.5 size-4 flex-shrink-0" />
                    <span>前后端自动化测试已全部通过，当前没有失败测试项。</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-[#e8e7e2] bg-white p-5 shadow-sm">
            <div className="mb-5 flex items-center gap-2">
              <GitBranch className="size-5 text-[#7c3aed]" />
              <h2 className="text-lg font-bold text-[#171717]">F1-F4 得分分布</h2>
            </div>
            <div className="space-y-4">
              {sections.map((section) => {
                const score = getSectionScore(section);
                return (
                  <div key={section.code}>
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span
                          className="rounded px-2 py-1 text-xs font-bold text-white"
                          style={{ background: section.color }}
                        >
                          {section.code}
                        </span>
                        <span className="text-sm font-semibold text-[#171717]">{section.title}</span>
                      </div>
                      <span className="text-sm font-bold text-[#525252]">
                        {score.scored}/{score.total}
                      </span>
                    </div>
                    <div className="h-3 overflow-hidden rounded-full bg-[#f3f2ee]">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${score.percent}%`, background: section.color }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-[#e8e7e2] bg-white shadow-sm">
          <div className="border-b border-[#e8e7e2] p-5">
            <h2 className="text-lg font-bold text-[#171717]">用例执行矩阵</h2>
            <p className="mt-1 text-sm text-[#525252]">
              评分口径：高优先级 5 分，中优先级 3 分；失败、阻塞、未执行均按 0 分计。
            </p>
          </div>
          <div className="divide-y divide-[#e8e7e2]">
            {sections.map((section) => (
              <div className="p-5" key={section.code}>
                <div className="mb-4 flex items-center gap-3">
                  <span
                    className="rounded px-2.5 py-1 text-sm font-bold text-white"
                    style={{ background: section.color }}
                  >
                    {section.code}
                  </span>
                  <h3 className="font-bold text-[#171717]">{section.title}</h3>
                </div>
                <div className="grid gap-3">
                  {section.cases.map((testCase) => {
                    const meta = statusMeta[testCase.status];
                    return (
                      <div
                        className="grid gap-3 rounded-lg border border-[#e8e7e2] bg-[#fafaf7] p-4 lg:grid-cols-[0.6fr_1.2fr_0.55fr_0.9fr]"
                        key={testCase.id}
                      >
                        <div>
                          <div className="text-xs font-bold text-[#8a8a8a]">{testCase.id}</div>
                          <div className="mt-1 text-sm font-bold text-[#171717]">
                            {testCase.priority}优先级 · {testCase.weight} 分
                          </div>
                        </div>
                        <div className="text-sm font-semibold leading-6 text-[#171717]">
                          {testCase.title}
                        </div>
                        <div>
                          <span
                            className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-bold ${meta.className}`}
                          >
                            <StatusIcon status={testCase.status} />
                            {meta.label}
                          </span>
                        </div>
                        <div className="text-sm leading-6 text-[#525252]">
                          <strong className="font-semibold text-[#171717]">{testCase.measured}</strong>
                          <br />
                          {testCase.evidence}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
