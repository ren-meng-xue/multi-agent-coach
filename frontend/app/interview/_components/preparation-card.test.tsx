import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { PreparationCard } from "./preparation-card";

const mockQuestions = [
  {
    id: 1,
    question: "请描述 CAP 理论",
    category: "technical" as const,
    focus_area: "分布式",
    priority: 1,
  },
  {
    id: 2,
    question: "项目中如何量化结果",
    category: "behavioral" as const,
    focus_area: "量化",
    priority: 1,
  },
];

test("running 状态显示准备中", () => {
  render(
    <PreparationCard
      status="running"
      nodes={[
        { id: "master", label: "MASTER", title: "识别方向，启动准备", status: "running", tokens: "" }
      ]}
      questions={[]}
      summary=""
      onStart={() => {}}
    />
  );
  expect(screen.getByText("正在调度")).toBeInTheDocument();
  expect(screen.getByText("识别方向，启动准备")).toBeInTheDocument();
});

test("done 状态显示准备完成和两个按钮", () => {
  render(
    <PreparationCard
      status="done"
      nodes={[]}
      questions={mockQuestions}
      summary="为你定制了 2 道题"
      onStart={() => {}}
    />
  );
  expect(screen.getByText("调度中心：准备就绪")).toBeInTheDocument();
  expect(screen.getByText(/开始本轮面试/)).toBeInTheDocument();
  expect(screen.getByText(/全量题目预览/)).toBeInTheDocument();
});

test("点击就绪切换展开", () => {
  render(
    <PreparationCard
      status="done"
      nodes={[]}
      questions={mockQuestions}
      summary="test"
      onStart={() => {}}
    />
  );
  const toggle = screen.getByRole("button", { name: /展开 AI 教练组详情/ });
  fireEvent.click(toggle);
  expect(screen.getByRole("button", { name: /收起 AI 教练组详情/ })).toBeInTheDocument();
});

test("点击先看题目列表在卡片内内联展开题目，不弹窗", () => {
  render(
    <PreparationCard
      status="done"
      nodes={[]}
      questions={mockQuestions}
      summary="test"
      onStart={() => {}}
    />
  );
  fireEvent.click(screen.getByRole("button", { name: /全量题目预览/ }));
  expect(screen.getByText("请描述 CAP 理论")).toBeInTheDocument();
  expect(screen.getByText("项目中如何量化结果")).toBeInTheDocument();
  // 没有弹窗遮罩
  expect(document.querySelector("[class*='fixed inset-0']")).not.toBeInTheDocument();
});

test("题目为空时内联展示占位提示", () => {
  render(
    <PreparationCard
      status="done"
      nodes={[]}
      questions={[]}
      summary="test"
      onStart={() => {}}
    />
  );
  fireEvent.click(screen.getByRole("button", { name: /全量题目预览/ }));
  expect(screen.getByText(/题目生成中/)).toBeInTheDocument();
});
