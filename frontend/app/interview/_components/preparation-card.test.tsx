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

test("当节点包含 reactSteps 时，渲染 ReactToolTree 组件", () => {
  render(
    <PreparationCard
      status="running"
      nodes={[
        {
          id: "research_agent",
          label: "调研",
          title: "正在调研",
          status: "running",
          tokens: "",
          reactStatus: "running",
          reactSteps: [
            {
              index: 0,
              thinkStatus: "running",
              thinkContent: "正在思考",
              toolCalls: [],
            },
          ],
        },
      ]}
    />
  );
  
  // 检查是否渲染了 ReactToolTree 里的特定文本
  expect(screen.getByText(/第 1 步思考与执行/)).toBeInTheDocument();
  expect(screen.getByText("正在思考")).toBeInTheDocument();
});
