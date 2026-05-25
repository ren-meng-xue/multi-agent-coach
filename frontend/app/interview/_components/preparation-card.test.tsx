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
      nodes={[]}
      questions={[]}
      summary=""
      onStart={() => {}}
    />
  );
  expect(screen.getByText(/就绪中/)).toBeInTheDocument();
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
  expect(screen.getByText("面试准备就绪")).toBeInTheDocument();
  expect(screen.getByText(/开始第\s*1\s*题/)).toBeInTheDocument();
  expect(screen.getByText(/先看题目列表/)).toBeInTheDocument();
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
  const toggle = screen.getByRole("button", { name: /就绪/ });
  fireEvent.click(toggle);
  expect(screen.getByRole("button", { name: /就绪/ })).toBeInTheDocument();
});
