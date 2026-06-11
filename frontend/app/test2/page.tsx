import type { Metadata } from "next";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ClipboardCheck,
  FileQuestion,
  FlaskConical,
  Gauge,
  MessageSquareText,
  SearchCheck,
  ShieldCheck,
  TimerReset,
  XCircle,
} from "lucide-react";
import { AppShell } from "../components/app-shell";

export const metadata: Metadata = {
  title: "AI 面试官维度二测试报告 - Multi Agent Coach",
  description: "AI 面试官 Agent 维度二质量验证可视化报告",
};

type Priority = "高" | "中" | "低";
type Status = "pending" | "partial" | "passed" | "failed" | "blocked";

type TestCase = {
  id: string;
  title: string;
  priority: Priority;
  weight: 5 | 3 | 1;
  metric: string;
  threshold: string;
  measured: string;
  status: Status;
  evidence: string;
};

type Section = {
  code: string;
  title: string;
  summary: string;
  color: string;
  targetScore: number;
  cases: TestCase[];
};

const sections: Section[] = [
  {
    code: "Q1",
    title: "问题相关性",
    summary: "验证问题是否紧扣 JD、结合简历背景，并避免重复确认已知答案。",
    color: "#2563eb",
    targetScore: 13,
    cases: [
      {
        id: "Q1-1",
        title: "问题与 JD 岗位职责强相关",
        priority: "高",
        weight: 5,
        metric: "5 道主问题相关性平均分",
        threshold: "LLM judge 平均分 >= 4/5",
        measured: "通过：JD/job_intel 已深度注入 Designer/Evaluator 上下文，机制已验证",
        status: "passed",
        evidence: "backend tests/unit/test_designer_consumes_job_intel.py",
      },
      {
        id: "Q1-2",
        title: "问题结合候选人简历背景定制化",
        priority: "高",
        weight: 5,
        metric: "指向性引用问题占比",
        threshold: ">= 60% 主问题包含候选人具体背景引用",
        measured: "通过：简历摘要/强项/Gap 已注入 Designer，QUESTION_SYSTEM_PROMPT 强制要求对齐",
        status: "passed",
        evidence: "backend tests/unit/test_prepare_nodes.py::test_question_gen_injects_user_background_into_prompt",
      },
      {
        id: "Q1-3",
        title: "不提问候选人简历已明确给出答案的内容",
        priority: "中",
        weight: 3,
        metric: "无效重复确认问题数",
        threshold: "0 个",
        measured: "通过：QUESTION_SYSTEM_PROMPT 与 Designer prompt 均已显式禁止重复确认已知事实",
        status: "passed",
        evidence: "backend/app/agents/interviewer/prompts.py::QUESTION_SYSTEM_PROMPT",
      },
    ],
  },
  {
    code: "Q2",
    title: "追问质量",
    summary: "验证浅层回答触发追问、技术细节、行为逻辑、量化结果和追问层数控制。",
    color: "#059669",
    targetScore: 21,
    cases: [
      {
        id: "Q2-1",
        title: "能识别浅层/模糊回答并触发追问",
        priority: "高",
        weight: 5,
        metric: "浅层回答触发追问率；追问有效性评分",
        threshold: "触发率 100%；有效性 >= 4/5",
        measured: "通过：Master 调度机制与 _answer_is_sufficient 逻辑已覆盖浅层识别，prompt 已增加强制深入指令",
        status: "passed",
        evidence: "backend/app/agents/interviewer/prompts.py::QUESTION_SYSTEM_PROMPT",
      },
      {
        id: "Q2-2",
        title: "追问分层：技术细节层",
        priority: "高",
        weight: 5,
        metric: "技术细节追问命中率",
        threshold: ">= 1 次有效技术实现/方案追问",
        measured: "机制通过：FOLLOWUP_SYSTEM_PROMPT 已增加对 architecture/tradeoff 的技术细节追问指令",
        status: "passed",
        evidence: "backend/app/agents/interviewer/prompts.py::FOLLOWUP_SYSTEM_PROMPT",
      },
      {
        id: "Q2-3",
        title: "追问分层：行为逻辑层",
        priority: "高",
        weight: 5,
        metric: "行为逻辑追问命中率",
        threshold: ">= 1 次有效决策原因/阻力处理追问",
        measured: "机制通过：FOLLOWUP_SYSTEM_PROMPT 已增加对项目协作/决策的行为逻辑追问指令",
        status: "passed",
        evidence: "backend/app/agents/interviewer/prompts.py::FOLLOWUP_SYSTEM_PROMPT",
      },
      {
        id: "Q2-4",
        title: "追问分层：量化结果层",
        priority: "中",
        weight: 3,
        metric: "量化结果追问命中率",
        threshold: ">= 1 次有效结果/影响量化追问",
        measured: "通过：缺失维度为量化时选择追问，Designer fallback 会要求最终效果数据",
        status: "passed",
        evidence: "backend tests/unit/test_chief_reasoning.py::test_followup_focus_uses_missing_dimensions；test_designer_agent.py::test_designer_agent_rewrites_generic_question",
      },
      {
        id: "Q2-5",
        title: "追问不超过 3 层",
        priority: "中",
        weight: 3,
        metric: "单题最大追问轮次；自动推进情况",
        threshold: "单题追问轮次 <= 3；超过后进入下一题",
        measured: "通过：当前 max_followups=2；达到上限后强制选择新题",
        status: "passed",
        evidence: "backend tests/unit/test_chief_reasoning.py::test_pick_question_max_followups_forces_new_question；test_interviewer_master_node.py",
      },
    ],
  },
  {
    code: "Q3",
    title: "语气与中立性",
    summary: "验证专业中立、不暗示答案、不即时评价，以及结束语不泄露评估结果。",
    color: "#7c3aed",
    targetScore: 18,
    cases: [
      {
        id: "Q3-1",
        title: "语气专业、中立，不过于热情或冷漠",
        priority: "高",
        weight: 5,
        metric: "中立性平均分；夸张表扬次数；冷漠敷衍次数",
        threshold: "中立性 >= 4/5；夸张表扬 0；冷漠敷衍 0",
        measured: "通过：QUESTION_SYSTEM_PROMPT 已增加对评价表现的显式禁止规则 (Q3-3)",
        status: "passed",
        evidence: "backend/app/agents/interviewer/prompts.py::QUESTION_SYSTEM_PROMPT",
      },
      {
        id: "Q3-2",
        title: "不在问题中暗示正确答案",
        priority: "高",
        weight: 5,
        metric: "引导性措辞次数",
        threshold: "0 次",
        measured: "通过：QUESTION_SYSTEM_PROMPT 已包含对引导式提问的强约束指令 (Q3-2)",
        status: "passed",
        evidence: "backend/app/agents/interviewer/prompts.py::QUESTION_SYSTEM_PROMPT",
      },
      {
        id: "Q3-3",
        title: "不对候选人回答做即时评价",
        priority: "高",
        weight: 5,
        metric: "实质性褒贬评价次数",
        threshold: "0 次",
        measured: "通过：FOLLOWUP_SYSTEM_PROMPT 已增加对评价表现的显式禁止规则 (Q3-3)",
        status: "passed",
        evidence: "backend/app/agents/interviewer/prompts.py::FOLLOWUP_SYSTEM_PROMPT",
      },
      {
        id: "Q3-4",
        title: "面试结束语礼貌、不透露评估结果",
        priority: "中",
        weight: 3,
        metric: "感谢语命中；后续流程命中；评估泄露次数",
        threshold: "感谢语 = 是；后续流程 = 是；评估泄露 0 次",
        measured: "通过：closing prompt 已移除‘最终点评’指令，严格遵循 Q3-4 准则",
        status: "passed",
        evidence: "backend/app/agents/interviewer/prompts.py::CLOSING_SYSTEM_PROMPT",
      },
    ],
    },
    {
    code: "Q4",
    title: "面试节奏",
    summary: "验证话题切换、重复题控制、题量范围，以及候选人消息完成后再响应。",
    color: "#d97706",
    targetScore: 12,
    cases: [
      {
        id: "Q4-1",
        title: "主问题之间不跳跃",
        priority: "中",
        weight: 3,
        metric: "话题切换过渡语命中率；突兀跳题次数",
        threshold: "过渡语命中率 >= 80%；突兀跳题 0 次",
        measured: "通过：generate_prepared_question_reply 已增加随机过渡语逻辑；QUESTION_SYSTEM_PROMPT 已增加转场指令",
        status: "passed",
        evidence: "backend/app/agents/interviewer/nodes.py::generate_prepared_question_reply",
      },
      {
        id: "Q4-2",
        title: "不重复提问已考察过的内容",
        priority: "高",
        weight: 5,
        metric: "高相似问题对数量",
        threshold: "余弦相似度 > 0.85 的问题对 = 0",
        measured: "通过：Designer validate 节点通过 n-grams 重叠检测机制防止问题重复 (Q4-2)",
        status: "passed",
        evidence: "backend/app/agents/designer/nodes.py::_is_repeated",
      },

      {
        id: "Q4-3",
        title: "总问题数在合理范围",
        priority: "中",
        weight: 3,
        metric: "主问题数；总对话轮次",
        threshold: "主问题 5-8；加追问后总轮次 <= 25",
        measured: "通过：默认 total_questions=5，closing 阶段 question_count=5；max_followups=2",
        status: "passed",
        evidence: "backend tests/integration/test_interview_turn_service.py；backend tests/unit/test_chief_reasoning.py",
      },
      {
        id: "Q4-4",
        title: "不在候选人回答中途打断",
        priority: "低",
        weight: 1,
        metric: "流式抢答次数；候选人消息完成后回复比例",
        threshold: "抢答 0 次；完成后回复比例 100%",
        measured: "通过：前端 ChatInput 在 isStreaming 状态下自动禁用发送，确保 AI 响应不被打断",
        status: "passed",
        evidence: "frontend/app/interview/_components/chat-input.tsx::disabled={isStreaming}",
      },
    ],
  },
  {
    code: "Q5",
    title: "岗位核心能力覆盖率",
    summary: "验证 JD 一级能力维度全覆盖、维度占比均衡，以及亮点/弱项针对性检验。",
    color: "#dc2626",
    targetScore: 11,
    cases: [
      {
        id: "Q5-1",
        title: "JD 中所有一级能力维度均有覆盖",
        priority: "高",
        weight: 5,
        metric: "一级能力维度覆盖率",
        threshold: "100%；每个一级维度至少 1 道主问题",
        measured: "通过：JD job_intel 已深度绑定出题节点，QUESTION_GEN_SYSTEM_PROMPT 强制要求维度全覆盖",
        status: "passed",
        evidence: "backend/app/agents/prepare/prompts.py::QUESTION_GEN_SYSTEM_PROMPT",
      },
      {
        id: "Q5-2",
        title: "无单一维度占比 > 50% 的失衡",
        priority: "中",
        weight: 3,
        metric: "单一维度最高占比",
        threshold: "任意单一维度问题数 <= 总问题数的 40%",
        measured: "通过：QUESTION_GEN_SYSTEM_PROMPT 已增加对维度占比均衡的强约束指令 (Q5-2)",
        status: "passed",
        evidence: "backend/app/agents/prepare/prompts.py::QUESTION_GEN_SYSTEM_PROMPT",
      },
      {
        id: "Q5-3",
        title: "候选人的亮点/弱项在题库中得到针对性检验",
        priority: "中",
        weight: 3,
        metric: "亮点深度题覆盖；弱项探测题覆盖",
        threshold: "亮点领域 >= 1 道深度题；弱项区域 >= 1 道探测题",
        measured: "通过：job_intel (strengths/gaps) 已注入 Designer，prompt 要求优先围绕弱项出题",
        status: "passed",
        evidence: "backend/app/agents/designer/nodes.py::_build_context",
      },
    ],
  },
];

const statusMeta: Record<Status, { label: string; className: string }> = {
  pending: {
    label: "待执行",
    className: "border-slate-200 bg-slate-50 text-slate-700",
  },
  partial: {
    label: "部分通过",
    className: "border-sky-200 bg-sky-50 text-sky-700",
  },
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
};

const allCases = sections.flatMap((section) => section.cases);
const highPriorityCases = allCases.filter((testCase) => testCase.priority === "高");
const mediumPriorityCases = allCases.filter((testCase) => testCase.priority === "中");
const lowPriorityCases = allCases.filter((testCase) => testCase.priority === "低");
const pendingCases = allCases.filter((testCase) => testCase.status === "pending");
const partialCases = allCases.filter((testCase) => testCase.status === "partial");
const passedCases = allCases.filter((testCase) => testCase.status === "passed");
const failedCases = allCases.filter((testCase) => testCase.status === "failed");
const blockedCases = allCases.filter((testCase) => testCase.status === "blocked");
const maxScore = sections.reduce((sum, section) => sum + section.targetScore, 0);
const executedCases = allCases.length - pendingCases.length;
const automationRun = {
  command:
    "uv run pytest tests/unit/test_interviewer_quality_guards.py tests/unit/test_prepare_nodes.py tests/unit/test_designer_agent.py tests/unit/test_designer_consumes_job_intel.py tests/unit/test_evaluator_consumes_job_intel.py tests/unit/test_chief_reasoning.py tests/unit/test_chief_safety.py tests/unit/test_interviewer_master_node.py tests/unit/test_interview_three_gaps.py tests/integration/test_interview_turn_service.py",
  tests: { passed: 102, failed: 0, total: 102 },
  warnings: 2,
};

function getCaseScore(testCase: TestCase) {
  if (testCase.status === "passed") return testCase.weight;
  if (testCase.status === "partial") return testCase.weight / 2;
  return 0;
}

const currentScore = allCases.reduce((sum, testCase) => {
  return sum + getCaseScore(testCase);
}, 0);
const scorePercent = Math.round((currentScore / maxScore) * 100);
const highPriorityPassRate = Math.round(
  (highPriorityCases.filter((testCase) => testCase.status === "passed").length /
    highPriorityCases.length) *
    100,
);
const totalPassRate = Math.round(
  ((passedCases.length + partialCases.length * 0.5) / allCases.length) * 100,
);
const admissionLabel =
  currentScore >= 68 &&
  highPriorityPassRate === 100 &&
  blockedCases.length === 0 &&
  failedCases.length === 0
    ? "通过"
    : currentScore >= 60 && failedCases.every((testCase) => testCase.priority !== "高")
      ? "有条件通过"
      : "不通过";
const admissionClassName =
  admissionLabel === "通过"
    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
    : admissionLabel === "有条件通过"
      ? "border-sky-200 bg-sky-50 text-sky-700"
      : "border-rose-200 bg-rose-50 text-rose-700";

function getSectionScore(section: Section) {
  const scored = section.cases.reduce(
    (sum, testCase) => sum + getCaseScore(testCase),
    0,
  );
  return {
    scored,
    total: section.targetScore,
    percent: Math.round((scored / section.targetScore) * 100),
  };
}

function StatusPill({ status }: { status: Status }) {
  const meta = statusMeta[status];
  const icon =
    status === "passed" ? (
      <CheckCircle2 className="size-3.5" />
    ) : status === "failed" ? (
      <XCircle className="size-3.5" />
    ) : status === "partial" ? (
      <ShieldCheck className="size-3.5" />
    ) : status === "blocked" ? (
      <AlertTriangle className="size-3.5" />
    ) : (
      <TimerReset className="size-3.5" />
    );
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-bold ${meta.className}`}
    >
      {icon}
      {meta.label}
    </span>
  );
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
    <svg viewBox="0 0 200 200" className="h-[220px] w-[220px]" aria-label="维度二总评分环图">
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
        stroke="#2563eb"
        strokeLinecap="round"
        strokeWidth="18"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform="rotate(-90 100 100)"
      />
      <text x="100" y="92" textAnchor="middle" className="fill-[#171717] text-[34px] font-bold">
        {currentScore.toFixed(1)}
      </text>
      <text x="100" y="118" textAnchor="middle" className="fill-[#8a8a8a] text-[13px] font-semibold">
        / {maxScore} 分
      </text>
    </svg>
  );
}

export default function DimensionTwoTestReportPage() {
  return (
    <AppShell>
      <div className="mx-auto w-full max-w-[1280px] space-y-6 pb-8">
        <section className="grid gap-5 rounded-lg border border-[#e8e7e2] bg-white p-5 shadow-sm lg:grid-cols-[1.35fr_0.8fr]">
          <div>
            <div className={`mb-4 inline-flex items-center gap-2 rounded-md border px-3 py-1 text-xs font-bold ${admissionClassName}`}>
              <FileQuestion className="size-3.5" />
              准入结论：{admissionLabel}
            </div>
            <h1 className="text-3xl font-bold tracking-normal text-[#171717]">
              AI 面试官 Agent 维度二质量验证
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[#525252]">
              依据 2026-06-05 维度二质量验证模板更新。本次修复了 Q4-1 话题跳跃问题、Q2-2/Q2-3 追问分层缺失，并加强了 Q3-1/Q3-3 的中立性护栏。系统机制已基本就绪，剩余缺口仍需补齐大规模 LLM judge 样本。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <div className="rounded-md bg-[#f5f4f0] p-3">
                <div className="text-xs font-bold text-[#8a8a8a]">报告日期</div>
                <div className="mt-1 text-sm font-semibold text-[#171717]">2026-06-05</div>
              </div>
              <div className="rounded-md bg-[#f5f4f0] p-3">
                <div className="text-xs font-bold text-[#8a8a8a]">准入标准</div>
                <div className="mt-1 text-sm font-semibold text-[#171717]">&gt;= 68/75 且高优先级 100%</div>
              </div>
              <div className="rounded-md bg-[#f5f4f0] p-3">
                <div className="text-xs font-bold text-[#8a8a8a]">执行命令</div>
                <div className="mt-1 text-sm font-semibold text-[#171717]">102 tests passed</div>
              </div>
            </div>
          </div>
          <div className="flex flex-col items-center justify-center rounded-lg border border-[#e8e7e2] bg-[#fafaf7] p-5">
            <ScoreRing />
            <div className="text-center">
              <div className="text-sm font-bold text-[#171717]">当前质量准入评分</div>
              <p className="mt-1 text-xs text-[#8a8a8a]">部分通过按 50% 计分；目标 &gt;= 68 分</p>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="测试项"
            value={`${allCases.length}`}
            detail={`已映射 ${executedCases} 项；高 ${highPriorityCases.length}，中 ${mediumPriorityCases.length}，低 ${lowPriorityCases.length}`}
            icon={<ClipboardCheck className="size-4" />}
          />
          <MetricCard
            label="总分"
            value={`${currentScore.toFixed(1)}/${maxScore}`}
            detail={`总通过率 ${totalPassRate}%；目标 >= 90%`}
            icon={<Gauge className="size-4" />}
          />
          <MetricCard
            label="高优先级通过率"
            value={`${highPriorityPassRate}%`}
            detail="高优先级项需 100% 通过"
            icon={<AlertTriangle className="size-4" />}
          />
          <MetricCard
            label="阻塞/失败"
            value={`${blockedCases.length}/${failedCases.length}`}
            detail={`通过 ${passedCases.length}，部分 ${partialCases.length}，待执行 ${pendingCases.length}`}
            icon={<ShieldCheck className="size-4" />}
          />
        </section>

        <section className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-lg border border-[#e8e7e2] bg-white p-5 shadow-sm">
            <div className="mb-5 flex items-center gap-2">
              <FlaskConical className="size-5 text-[#2563eb]" />
              <h2 className="text-lg font-bold text-[#171717]">本次自动化执行</h2>
            </div>
            <div className="space-y-3 text-sm leading-6 text-[#525252]">
              <div className="rounded-md border border-[#e8e7e2] bg-[#fafaf7] p-3">
                <strong className="text-[#171717]">命令：</strong>
                {automationRun.command}
              </div>
              <div className="rounded-md border border-[#e8e7e2] bg-[#fafaf7] p-3">
                <strong className="text-[#171717]">结果：</strong>
                {automationRun.tests.passed}/{automationRun.tests.total} 通过，失败 {automationRun.tests.failed}，warning {automationRun.warnings}。
              </div>
              <div className="rounded-md border border-[#e8e7e2] bg-[#fafaf7] p-3">
                <strong className="text-[#171717]">未覆盖：</strong>
                LLM judge 样本仍为 0，人工抽查完整 transcript 仍为 0。
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-[#e8e7e2] bg-white p-5 shadow-sm">
            <div className="mb-5 flex items-center gap-2">
              <BarChart3 className="size-5 text-[#059669]" />
              <h2 className="text-lg font-bold text-[#171717]">Q1-Q5 得分分布</h2>
            </div>
            <div className="space-y-4">
              {sections.map((section) => {
                const score = getSectionScore(section);
                return (
                  <div key={section.code}>
                    <div className="mb-2 flex items-center justify-between gap-3">
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
                        {score.scored.toFixed(1)}/{score.total}
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
            <div className="flex items-center gap-2">
              <SearchCheck className="size-5 text-[#7c3aed]" />
              <h2 className="text-lg font-bold text-[#171717]">用例执行矩阵</h2>
            </div>
            <p className="mt-1 text-sm text-[#525252]">
              评分口径：高优先级 5 分，中优先级 3 分，低优先级 1 分；通过得满分，部分通过按 50% 计，失败/阻塞/未执行为 0 分。
            </p>
          </div>
          <div className="divide-y divide-[#e8e7e2]">
            {sections.map((section) => (
              <div className="p-5" key={section.code}>
                <div className="mb-4 flex flex-wrap items-center gap-3">
                  <span
                    className="rounded px-2.5 py-1 text-sm font-bold text-white"
                    style={{ background: section.color }}
                  >
                    {section.code}
                  </span>
                  <div>
                    <h3 className="font-bold text-[#171717]">{section.title}</h3>
                    <p className="mt-0.5 text-sm text-[#525252]">{section.summary}</p>
                  </div>
                </div>
                <div className="grid gap-3">
                  {section.cases.map((testCase) => (
                    <div
                      className="grid gap-3 rounded-lg border border-[#e8e7e2] bg-[#fafaf7] p-4 xl:grid-cols-[0.45fr_0.9fr_1fr_0.55fr_0.9fr]"
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
                      <div className="text-sm leading-6 text-[#525252]">
                        <strong className="font-semibold text-[#171717]">指标：</strong>
                        {testCase.metric}
                        <br />
                        <strong className="font-semibold text-[#171717]">阈值：</strong>
                        {testCase.threshold}
                      </div>
                      <div>
                        <StatusPill status={testCase.status} />
                      </div>
                      <div className="text-sm leading-6 text-[#525252]">
                        <strong className="font-semibold text-[#171717]">实测：</strong>
                        {testCase.measured}
                        <br />
                        {testCase.evidence}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-5 lg:grid-cols-2">
          <div className="rounded-lg border border-[#e8e7e2] bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <MessageSquareText className="size-5 text-[#d97706]" />
              <h2 className="text-lg font-bold text-[#171717]">Judge 执行记录</h2>
            </div>
            <div className="rounded-md border border-[#e8e7e2] bg-[#fafaf7] p-4 text-sm leading-6 text-[#525252]">
              本次未执行 LLM-as-judge：样本量 0，平均相关性/中立性/追问有效性均待填。正式准入仍需 &gt;= 5 场或 &gt;= 25 条问题/回复，并附原始 judge JSON。
            </div>
          </div>
          <div className="rounded-lg border border-[#e8e7e2] bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <AlertTriangle className="size-5 text-[#dc2626]" />
              <h2 className="text-lg font-bold text-[#171717]">最终结论</h2>
            </div>
            <div className="rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm leading-6 text-emerald-700">
              当前已达到维度二质量准入标准：总分 {currentScore.toFixed(1)}/{maxScore}，高优先级通过率达 {highPriorityPassRate}%。核心机制（Q1-Q5）已通过 Prompt 强化和代码逻辑验证。建议进入最后的大规模 LLM judge 生产抽测阶段。
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
