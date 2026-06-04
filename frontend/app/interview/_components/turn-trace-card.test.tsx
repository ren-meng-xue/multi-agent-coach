import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { TurnTraceCard } from "./turn-trace-card";

describe("TurnTraceCard", () => {
  it("renders running state with turn index", () => {
    render(
      <TurnTraceCard
        status="running"
        nodes={[
          { id: "master", label: "MASTER", status: "running", tokens: "" },
        ]}
        turnIndex={2}
      />,
    );
    expect(
      screen.getByText(/多 AGENT · 正在分析 · 第 1 轮/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/第 1 轮/)).toBeInTheDocument();
  });

  it("renders done state with summary score", () => {
    render(
      <TurnTraceCard
        status="done"
        nodes={[
          {
            id: "master",
            label: "MASTER",
            status: "done",
            tokens: "评估并追问",
            elapsedMs: 120,
          },
          {
            id: "evaluator",
            label: "评估",
            status: "done",
            tokens: "·覆盖CAP",
            elapsedMs: 280,
          },
          {
            id: "followup",
            label: "面试官 · 追问",
            status: "done",
            tokens: "",
            elapsedMs: 950,
          },
        ]}
        turnIndex={2}
        summaryScore={7.4}
      />,
    );
    expect(
      screen.getByText(/多 Agent · 分析完成 · 第 1 轮/),
    ).toBeInTheDocument();

    // Toggle the card to reveal inner contents
    fireEvent.click(screen.getByText(/查看 AI 思考过程/));
    expect(screen.getByText(/7\.4/)).toBeInTheDocument();
  });

  it("renders error state when error is passed", () => {
    render(
      <TurnTraceCard
        status="done"
        nodes={[
          {
            id: "master",
            label: "MASTER",
            status: "done",
            tokens: "分析完成",
            elapsedMs: 120,
          },
        ]}
        turnIndex={2}
        error="AI 暂时无法响应，请稍后重试"
      />,
    );
    expect(screen.getByText("AI 暂时无法响应，请稍后重试")).toBeInTheDocument();
  });

  it("点击展开后按钮文案变为收起思考过程", () => {
    render(
      <TurnTraceCard
        status="done"
        nodes={[
          { id: "chief_think", label: "思考", status: "done", tokens: "" },
        ]}
        turnIndex={2}
      />,
    );
    fireEvent.click(screen.getByText(/查看 AI 思考过程/));
    expect(screen.getByText(/收起思考过程/)).toBeInTheDocument();
  });

  it("折叠状态下 designedQuestion 文本不可见", () => {
    const { queryByText } = render(
      <TurnTraceCard
        status="done"
        nodes={[
          {
            id: "ask_question",
            label: "出题",
            status: "done",
            tokens: "",
            designedQuestion: "请解释 CAP 定理",
          },
        ]}
        turnIndex={2}
      />,
    );
    // TurnTraceCard header 不渲染 designedQuestion，折叠时内容不可见
    expect(queryByText("请解释 CAP 定理")).toBeNull();
  });
});
