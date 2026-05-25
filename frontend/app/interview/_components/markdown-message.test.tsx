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

  it("渲染带有 ▎ 装饰符的引用块，并能智能合并中文硬换行，防止挤压折行", () => {
    render(
      <MarkdownMessage
        content={
          "我们的优化流程分三步。\n  ▎ 第一步：量化问题。先从 LangSmith 里导出性能差的 case，比如 decide_next\n  ▎ 节点误判率高，我会按\"弱回答被判 next_question\"。"
        }
        isUser={false}
      />
    );

    expect(screen.getByText("我们的优化流程分三步。")).toBeInTheDocument();
    expect(
      screen.getByText(
        /第一步：量化问题。先从 LangSmith 里导出性能差的 case，比如 decide_next节点误判率高，我会按"弱回答被判 next_question"/
      )
    ).toBeInTheDocument();
  });

  it("渲染带有 [ ] 和 [x] 的任务列表（Todo List）", () => {
    render(
      <MarkdownMessage
        content={"- [ ] 待办任务一\n- [x] 已完成任务二"}
        isUser={false}
      />
    );

    expect(screen.getByText("待办任务一")).toBeInTheDocument();
    expect(screen.getByText("已完成任务二")).toBeInTheDocument();

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(2);
    expect(checkboxes[0]).not.toBeChecked();
    expect(checkboxes[1]).toBeChecked();
  });

  it("渲染 # 至 ###### 各级标题块并包含正确标签样式", () => {
    render(
      <MarkdownMessage
        content={"# 标题一\n## 标题二\n### 标题三\n#### 标题四\n##### 标题五\n###### 标题六"}
        isUser={false}
      />
    );

    const h1 = screen.getByText("标题一");
    const h2 = screen.getByText("标题二");
    const h3 = screen.getByText("标题三");
    const h4 = screen.getByText("标题四");
    const h5 = screen.getByText("标题五");
    const h6 = screen.getByText("标题六");

    expect(h1.tagName).toBe("H1");
    expect(h2.tagName).toBe("H2");
    expect(h3.tagName).toBe("H3");
    expect(h4.tagName).toBe("H4");
    expect(h5.tagName).toBe("H5");
    expect(h6.tagName).toBe("H6");
  });

  it("渲染分割线 (Thematic Break)", () => {
    const { container } = render(
      <MarkdownMessage
        content={"第一部分\n---\n第二部分\n***\n第三部分"}
        isUser={false}
      />
    );

    expect(screen.getByText("第一部分")).toBeInTheDocument();
    expect(screen.getByText("第二部分")).toBeInTheDocument();
    expect(screen.getByText("第三部分")).toBeInTheDocument();
    
    const hrs = container.querySelectorAll("hr");
    expect(hrs).toHaveLength(2);
  });

  it("智能合并中文硬折行，但精细保留带句尾标点的故意换行", () => {
    const { container } = render(
      <MarkdownMessage
        content={
          "第一句段落内容。\n第二句也是独立的段落，这里有冒号：\n这里是子内容段落，但是这一行末尾没有标点符号\n这里直接相连，应该被合并。"
        }
        isUser={false}
      />
    );

    // 第一句带“。”，应该保留换行，不能被直接与第二句拼在一起。
    // 第二句带“：”，也应该保留换行。
    // 第三句末尾没有标点符号，应该与第四句合并。
    const p = container.querySelector("p");
    expect(p).toBeInTheDocument();
    expect(p?.textContent).toBe(
      "第一句段落内容。\n第二句也是独立的段落，这里有冒号：\n这里是子内容段落，但是这一行末尾没有标点符号这里直接相连，应该被合并。"
    );
  });
});
