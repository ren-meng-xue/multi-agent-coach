import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReactToolTree } from "./react-tool-tree";
import type { ReactIteration } from "@/lib/prepare-types";

describe("ReactToolTree", () => {
  it("renders null if steps are empty", () => {
    const { container } = render(<ReactToolTree steps={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("默认 running 状态展开，可以看到内容", () => {
    const steps: ReactIteration[] = [
      {
        index: 0,
        thinkStatus: "running",
        thinkContent: "我要开始调研了",
        toolCalls: [],
      },
      {
        index: 1,
        thinkStatus: "done",
        thinkContent: "现在调用工具",
        toolCalls: [
          {
            stepId: "c1",
            toolName: "web_search",
            status: "done",
            argsSummary: 'query="分布式"',
            resultSummary: "[10 条结果]",
            elapsedMs: 1200,
          },
          {
            stepId: "c2",
            toolName: "extract_jd",
            status: "error",
            argsSummary: 'text="..."',
            error: "解析超时",
            elapsedMs: 3000,
          },
        ],
      },
    ];

    render(<ReactToolTree steps={steps} isFinished={false} />);

    // 外层开关显示"收起"（当前已展开）
    expect(screen.getByText(/收起 ReAct 思考链/)).toBeInTheDocument();

    // 迭代标签
    expect(screen.getByText("第 1 轮")).toBeInTheDocument();
    expect(screen.getByText("第 2 轮")).toBeInTheDocument();

    // 内容渲染
    expect(screen.getByText("我要开始调研了")).toBeInTheDocument();
    expect(screen.getByText("现在调用工具")).toBeInTheDocument();

    // 工具渲染（resultSummary/error 以"↳ ..."形式呈现，用 regex 匹配）
    expect(screen.getByText("web_search")).toBeInTheDocument();
    expect(screen.getByText(/10 条结果/)).toBeInTheDocument();
    expect(screen.getByText("1.2s")).toBeInTheDocument();

    expect(screen.getByText("extract_jd")).toBeInTheDocument();
    expect(screen.getByText(/解析超时/)).toBeInTheDocument();
    expect(screen.getByText("3.0s")).toBeInTheDocument();
  });

  it("isFinished=true 时默认折叠，内容不可见", () => {
    const steps: ReactIteration[] = [
      { index: 0, thinkStatus: "done", thinkContent: "step 1", toolCalls: [] },
      { index: 1, thinkStatus: "done", thinkContent: "step 2", toolCalls: [] },
    ];
    render(<ReactToolTree steps={steps} isFinished={true} />);

    // 外层开关显示"展开"
    expect(screen.getByText(/展开 ReAct 思考链/)).toBeInTheDocument();
    // 内容不可见
    expect(screen.queryByText("第 1 轮")).toBeNull();
    expect(screen.queryByText("step 1")).toBeNull();
  });

  it("isFinished=true 时点击展开后可见内容", () => {
    const steps: ReactIteration[] = [
      { index: 0, thinkStatus: "done", thinkContent: "step 1", toolCalls: [] },
    ];
    render(<ReactToolTree steps={steps} isFinished={true} />);

    fireEvent.click(screen.getByText(/展开 ReAct 思考链/));

    expect(screen.getByText("第 1 轮")).toBeInTheDocument();
    expect(screen.getByText("step 1")).toBeInTheDocument();
    // 开关文字变为"收起"
    expect(screen.getByText(/收起 ReAct 思考链/)).toBeInTheDocument();
  });

  it("isFinished=false 时点击后折叠", () => {
    const steps: ReactIteration[] = [
      {
        index: 0,
        thinkStatus: "running",
        thinkContent: "thinking",
        toolCalls: [],
      },
    ];
    render(<ReactToolTree steps={steps} isFinished={false} />);

    // 默认展开
    expect(screen.getByText("第 1 轮")).toBeInTheDocument();

    // 点击折叠
    fireEvent.click(screen.getByText(/收起 ReAct 思考链/));
    expect(screen.queryByText("第 1 轮")).toBeNull();
  });
});
