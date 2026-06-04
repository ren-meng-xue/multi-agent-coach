import { render, screen, fireEvent } from "@testing-library/react";
import { expect, test } from "vitest";

import { TraceNode } from "./trace-node";

test("pending 状态显示灰色圆圈", () => {
  render(
    <TraceNode
      id="master"
      label="MASTER"
      title="识别方向"
      status="pending"
      tokens=""
    />,
  );
  expect(screen.getByTestId("trace-node-master")).toBeInTheDocument();
  expect(screen.getByTestId("trace-status-pending")).toBeInTheDocument();
});

test("running 状态显示动画圆圈", () => {
  render(
    <TraceNode
      id="master"
      label="MASTER"
      title="识别方向"
      status="running"
      tokens="检查用户档案"
    />,
  );
  expect(screen.getByTestId("trace-status-running")).toBeInTheDocument();
  expect(screen.getByText("检查用户档案")).toBeInTheDocument();
});

test("非 master 节点 running 时显示 token 内容", () => {
  render(
    <TraceNode
      id="memory_search"
      label="记忆检索"
      title="读取历史"
      status="running"
      tokens="正在查询数据库"
    />,
  );
  expect(screen.getByTestId("trace-status-running")).toBeInTheDocument();
  expect(screen.getByText("正在读取历史表现...")).toBeInTheDocument();
});

test("done 状态显示绿色勾 + 耗时", () => {
  render(
    <TraceNode
      id="master"
      label="MASTER"
      title="识别方向"
      status="done"
      tokens="检查完毕"
      elapsedMs={62}
    />,
  );
  expect(screen.getByTestId("trace-status-done")).toBeInTheDocument();
  expect(screen.getByText("62ms")).toBeInTheDocument();
});

test("evaluator done 且带有候选人画像时渲染 chips", () => {
  render(
    <TraceNode
      id="evaluator"
      label="评估官"
      title="评估"
      status="done"
      tokens="已评分"
      candidateLevel="junior"
      latentSignals={["architecture", "scaling"]}
      missingDimensions={["quantification"]}
    />,
  );
  expect(screen.getByText("初级")).toBeInTheDocument();
  expect(screen.getByText("architecture")).toBeInTheDocument();
  expect(screen.getByText("scaling")).toBeInTheDocument();
  expect(screen.getByText(/缺失：quantification/)).toBeInTheDocument();
});

test("evaluator 无画像数据时不渲染额外区域", () => {
  const { queryByText } = render(
    <TraceNode
      id="evaluator"
      label="评估官"
      title="评估"
      status="done"
      tokens="已评分"
    />,
  );
  expect(queryByText("缺失")).toBeNull();
});

test("research_agent 有 reactSteps 时渲染 ReactToolTree（running 默认展开）", () => {
  render(
    <TraceNode
      id="research_agent"
      label="岗位调研"
      title="通过 MCP 调研目标岗位"
      status="running"
      tokens=""
      reactSteps={[
        {
          index: 0,
          thinkContent: "我先调研目标岗位",
          thinkStatus: "done",
          toolCalls: [],
        },
      ]}
    />,
  );
  expect(screen.getByTestId("react-tool-tree")).toBeInTheDocument();
  // running 状态默认展开，内容可见
  expect(screen.getByText("我先调研目标岗位")).toBeInTheDocument();
});

test("research_agent 无 reactSteps 时不渲染 ReactToolTree", () => {
  const { queryByTestId } = render(
    <TraceNode
      id="research_agent"
      label="岗位调研"
      title="通过 MCP 调研目标岗位"
      status="running"
      tokens=""
    />,
  );
  expect(queryByTestId("react-tool-tree")).toBeNull();
});

test("research_agent reactSteps 含工具调用时渲染工具名（done 状态需展开）", () => {
  render(
    <TraceNode
      id="research_agent"
      label="岗位调研"
      title="通过 MCP 调研目标岗位"
      status="done"
      tokens=""
      reactStatus="done"
      reactSteps={[
        {
          index: 0,
          thinkContent: "调用工具",
          thinkStatus: "done",
          toolCalls: [
            {
              stepId: "t-0-c1",
              toolName: "extract_jd_text",
              argsSummary: 'text="..."',
              status: "done",
              resultSummary: "{title, company}",
              elapsedMs: 1200,
            },
          ],
        },
      ]}
    />,
  );
  // done 状态默认折叠，需手动展开
  fireEvent.click(screen.getByText(/展开 ReAct 思考链/));
  expect(screen.getByTestId("tool-call-extract_jd_text")).toBeInTheDocument();
  expect(screen.getByText("extract_jd_text")).toBeInTheDocument();
});

test("非 research_agent 节点有 reactSteps 时不渲染 ReactToolTree", () => {
  const { queryByTestId } = render(
    <TraceNode
      id="memory_search"
      label="记忆检索"
      title="读取历史"
      status="done"
      tokens=""
      reactSteps={[
        {
          index: 0,
          thinkContent: "Think A",
          thinkStatus: "done",
          toolCalls: [],
        },
      ]}
    />,
  );
  expect(queryByTestId("react-tool-tree")).toBeNull();
});

test("chief_think done 时渲染工具调用和画像 chips", () => {
  render(
    <TraceNode
      id="chief_think"
      label="思考"
      title="规划工具调用"
      status="done"
      tokens="准备评估并出题"
      candidateLevel="mid"
      latentSignals={["量化意识"]}
      missingDimensions={["边界条件"]}
      chiefToolCalls={["evaluate_answer", "design_question"]}
    />,
  );
  expect(screen.getByText("评估回答")).toBeInTheDocument();
  expect(screen.getByText("设计新题")).toBeInTheDocument();
  expect(screen.getByText("中级")).toBeInTheDocument();
  expect(screen.getByText("量化意识")).toBeInTheDocument();
  expect(screen.getByText(/缺失：边界条件/)).toBeInTheDocument();
});

// 记忆检索 done 展示记录数和红色薄弱点
test("memory_search done 显示记录数和红色薄弱点文本", () => {
  render(
    <TraceNode
      id="memory_search"
      label="记忆检索"
      title="读取历史表现"
      status="done"
      tokens=""
      weakAreas={["系统设计", "并发编程"]}
      recordCount={2}
    />,
  );
  expect(screen.getByText(/读取到 2 条记录/)).toBeInTheDocument();
  expect(screen.getByText(/系统设计、并发编程/)).toBeInTheDocument();
});

test("memory_search done 无 weakAreas 时显示暂无薄弱点提示", () => {
  render(
    <TraceNode
      id="memory_search"
      label="记忆检索"
      title="读取历史表现"
      status="done"
      tokens=""
      weakAreas={[]}
    />,
  );
  expect(screen.getByText("暂无历史薄弱点记录")).toBeInTheDocument();
});

test("research_agent done 展示 ReAct 轮次、公司名、Gap badge", () => {
  render(
    <TraceNode
      id="research_agent"
      label="岗位调研"
      title="调研目标岗位"
      status="done"
      tokens=""
      reactIterations={3}
      reactToolCount={5}
      companyName="字节跳动"
      gaps={["分布式", "并发"]}
    />,
  );
  expect(screen.getByText(/3 轮 · 5 次工具调用/)).toBeInTheDocument();
  expect(screen.getByText("字节跳动")).toBeInTheDocument();
  expect(screen.getByText(/Gap：分布式 · 并发/)).toBeInTheDocument();
});

test("jd_analysis done 展示公司、岗位、难度和技能 badge", () => {
  render(
    <TraceNode
      id="jd_analysis"
      label="JD分析"
      title="构建岗位考点"
      status="done"
      tokens=""
      jdCompany="字节跳动"
      jdRole="前端工程师"
      jdDifficulty="hard"
      jdKeySkills={["React", "性能优化"]}
    />,
  );
  expect(
    screen.getByText(/字节跳动 · 前端工程师 · 难度 hard/),
  ).toBeInTheDocument();
  expect(screen.getByText("React")).toBeInTheDocument();
  expect(screen.getByText("性能优化")).toBeInTheDocument();
});

test("question_gen done 展示总题数和非零分类统计", () => {
  render(
    <TraceNode
      id="question_gen"
      label="出题"
      title="定制专属题目"
      status="done"
      tokens=""
      questionTotal={5}
      questionStats={{ technical: 3, behavioral: 1, system_design: 1 }}
    />,
  );
  expect(screen.getByText(/已定制 5 道/)).toBeInTheDocument();
  expect(screen.getByText(/技术 ×3/)).toBeInTheDocument();
  expect(screen.getByText(/行为 ×1/)).toBeInTheDocument();
  expect(screen.getByText(/系统设计 ×1/)).toBeInTheDocument();
});

test("followup done 展示追问方向（missingDimensions）", () => {
  render(
    <TraceNode
      id="followup"
      label="追问"
      title="生成追问"
      status="done"
      tokens=""
      missingDimensions={["量化结果", "边界条件"]}
    />,
  );
  expect(screen.getByText(/追问方向：量化结果 · 边界条件/)).toBeInTheDocument();
});
