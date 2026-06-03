import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReactToolTree } from "./react-tool-tree";
import type { ReactIteration } from "@/lib/prepare-types";

describe("ReactToolTree", () => {
  it("renders null if steps are empty", () => {
    const { container } = render(<ReactToolTree steps={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders steps correctly", () => {
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
            elapsedMs: 250,
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

    // 标题渲染
    expect(screen.getByText(/第 1 步思考与执行/)).toBeInTheDocument();
    expect(screen.getByText(/第 2 步思考与执行/)).toBeInTheDocument();

    // 内容渲染
    expect(screen.getByText("我要开始调研了")).toBeInTheDocument();
    expect(screen.getByText("现在调用工具")).toBeInTheDocument();

    // 工具渲染
    expect(screen.getByText("web_search")).toBeInTheDocument();
    expect(screen.getByText('query="分布式"')).toBeInTheDocument();
    expect(screen.getByText("[10 条结果]")).toBeInTheDocument();
    expect(screen.getByText("250ms")).toBeInTheDocument();

    expect(screen.getByText("extract_jd")).toBeInTheDocument();
    expect(screen.getByText('text="..."')).toBeInTheDocument();
    expect(screen.getByText("解析超时")).toBeInTheDocument();
    expect(screen.getByText("3000ms")).toBeInTheDocument();
  });

  it("opens the last step by default if not finished", () => {
    const steps: ReactIteration[] = [
      { index: 0, thinkStatus: "done", thinkContent: "1", toolCalls: [] },
      { index: 1, thinkStatus: "running", thinkContent: "2", toolCalls: [] },
    ];
    render(<ReactToolTree steps={steps} isFinished={false} />);
    const details = screen.getAllByRole("group"); // <details> 没特别设置 role 时可能是 group
    // 我们可以直接通过 open 属性判断
    const elements = document.querySelectorAll("details");
    expect(elements[0].open).toBe(false);
    expect(elements[1].open).toBe(true);
  });

  it("closes all steps if finished", () => {
    const steps: ReactIteration[] = [
      { index: 0, thinkStatus: "done", thinkContent: "1", toolCalls: [] },
      { index: 1, thinkStatus: "done", thinkContent: "2", toolCalls: [] },
    ];
    render(<ReactToolTree steps={steps} isFinished={true} />);
    const elements = document.querySelectorAll("details");
    expect(elements[0].open).toBe(false);
    expect(elements[1].open).toBe(false);
  });
});