import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownMessage } from "./markdown-message";

describe("MarkdownMessage", () => {
  it("渲染段落、粗体和行内代码", () => {
    render(<MarkdownMessage content={"请说明 **一致性** 和 `CAP`。"} isUser={false} />);

    expect(screen.getByText("一致性")).toBeInTheDocument();
    expect(screen.getByText("一致性").tagName).toBe("STRONG");
    expect(screen.getByText("CAP").tagName).toBe("CODE");
  });

  it("渲染无序列表和有序列表", () => {
    render(
      <MarkdownMessage
        content={"- 分片策略\n- 容错设计\n\n1. 先讲方案\n2. 再讲权衡"}
        isUser={false}
      />,
    );

    expect(screen.getByText("分片策略")).toBeInTheDocument();
    expect(screen.getByText("容错设计")).toBeInTheDocument();
    expect(screen.getByText("先讲方案")).toBeInTheDocument();
    expect(screen.getByText("再讲权衡")).toBeInTheDocument();
  });

  it("渲染代码块并保留代码文本", () => {
    render(<MarkdownMessage content={"```ts\nconst ok = true;\n```"} isUser={false} />);

    const code = screen.getByText("const ok = true;");
    expect(code.tagName).toBe("CODE");
    expect(code).toHaveAttribute("data-language", "ts");
  });
});
