import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { PreparationCard } from "./preparation-card";

test("running 状态显示准备中", () => {
  render(
    <PreparationCard
      status="running"
      nodes={[
        { id: "master", label: "MASTER", title: "识别方向，启动准备", status: "running", tokens: "" }
      ]}
    />
  );
  expect(screen.getByText("正在调度")).toBeInTheDocument();
  expect(screen.getByText("识别方向，启动准备")).toBeInTheDocument();
});

test("done 状态显示准备就绪", () => {
  render(
    <PreparationCard
      status="done"
      nodes={[]}
    />
  );
  expect(screen.getByText("调度中心：准备就绪")).toBeInTheDocument();
});

test("done 状态有节点时默认展开准备阶段思考过程", () => {
  render(
    <PreparationCard
      status="done"
      nodes={[
        {
          id: "master",
          label: "MASTER",
          title: "识别方向，启动准备",
          status: "done",
          tokens: "• 用户目标是Senior Developer岗位。",
        },
      ]}
    />
  );
  expect(screen.getByText("AI 思考过程 - 准备阶段")).toBeInTheDocument();
  expect(screen.getByText("调度")).toBeInTheDocument();
  expect(screen.getByText("用户目标是Senior Developer岗位。")).toBeInTheDocument();
  expect(screen.getByText(/收起专家组详情/)).toBeInTheDocument();
});

test("点击按钮可切换展开/收起", () => {
  render(
    <PreparationCard
      status="done"
      nodes={[{ id: "master", label: "MASTER", title: "识别方向，启动准备", status: "done", tokens: "" }]}
    />
  );
  const toggle = screen.getByRole("button");
  expect(screen.getByText(/收起专家组详情/)).toBeInTheDocument();
  fireEvent.click(toggle);
  expect(screen.getByText(/展开专家组详情/)).toBeInTheDocument();
});

test("direction 显示在标题行", () => {
  render(
    <PreparationCard
      status="done"
      nodes={[]}
      direction="前端工程师"
    />
  );
  expect(screen.getByText("前端工程师")).toBeInTheDocument();
});
