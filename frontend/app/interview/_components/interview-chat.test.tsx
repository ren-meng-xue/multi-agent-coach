import { beforeEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InterviewChat } from "./interview-chat";
import { streamInterviewChat } from "@/lib/interview-chat";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: vi.fn().mockResolvedValue("test-token"),
  }),
}));

vi.mock("@/lib/interview-chat", () => ({
  streamInterviewChat: vi.fn(),
  resetInterviewSession: vi.fn().mockResolvedValue(undefined),
}));

const mockStreamInterviewChat = vi.mocked(streamInterviewChat);

describe("InterviewChat", () => {
  let writeTextMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useRealTimers();
    mockStreamInterviewChat.mockReset();
    writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: writeTextMock,
      },
      configurable: true,
      writable: true,
    });
  });

  it("输入栏固定在聊天面板底部，长内容只滚动消息区", () => {
    render(<InterviewChat />);

    const form = screen.getByRole("form", { name: "面试输入栏" });
    expect(form).toHaveClass("sticky", "bottom-0", "shrink-0");
  });

  it("输入框不展示浏览器历史输入记录", () => {
    render(<InterviewChat />);

    expect(screen.getByLabelText("输入面试练习内容")).toHaveAttribute("autocomplete", "off");
  });

  it("发送后渲染用户消息并流式拼接面试官回复", async () => {
    mockStreamInterviewChat.mockImplementation(async ({ onDelta, onState }) => {
      onState?.({ stage: "interview", question_count: 1, total_questions: 5 });
      onDelta("请先介绍");
      onDelta("一个项目。");
    });

    render(<InterviewChat />);

    await userEvent.type(screen.getByLabelText("输入面试练习内容"), "练分布式系统");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.getByText("练分布式系统")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("请先介绍一个项目。")).toBeInTheDocument();
    });
    expect(mockStreamInterviewChat).toHaveBeenCalledWith(
      expect.objectContaining({
        token: "test-token",
        message: "练分布式系统",
      }),
    );
    expect(screen.getByText("第 1/5 题")).toBeInTheDocument();
    expect(screen.getByText("正式面试进行中")).toBeInTheDocument();
  });

  it("将一帧内的多个 delta 合并后再渲染", async () => {
    let pendingFrame: FrameRequestCallback | null = null;
    const requestAnimationFrameSpy = vi
      .spyOn(window, "requestAnimationFrame")
      .mockImplementation((callback) => {
        pendingFrame = callback;
        return 1;
      });
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation((id) => {
      if (id === 1) pendingFrame = null;
    });

    let resolveStream: () => void = () => undefined;
    mockStreamInterviewChat.mockImplementation(async ({ onDelta }) => {
      onDelta("请");
      onDelta("详细");
      onDelta("描述");
      await new Promise<void>((resolve) => {
        resolveStream = resolve;
      });
    });

    render(<InterviewChat />);

    await userEvent.type(screen.getByLabelText("输入面试练习内容"), "练分布式系统");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => expect(requestAnimationFrameSpy).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("请详细描述")).not.toBeInTheDocument();

    await act(async () => {
      pendingFrame?.(performance.now());
    });

    expect(screen.getByText("请详细描述")).toBeInTheDocument();

    await act(async () => {
      resolveStream();
    });
  });

  it("流式请求失败后显示错误气泡并恢复输入", async () => {
    mockStreamInterviewChat.mockRejectedValue(new Error("AI 暂时无法响应"));

    render(<InterviewChat />);

    const input = screen.getByLabelText("输入面试练习内容");
    await userEvent.type(input, "练 JVM");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(screen.getByText("AI 暂时无法响应")).toBeInTheDocument();
    });
    expect(input).not.toBeDisabled();
  });

  it("初始渲染时复制按钮已启用（有开场引导消息）", () => {
    render(<InterviewChat />);
    const copyButton = screen.getByRole("button", { name: /复制会话/i });
    expect(copyButton).not.toBeDisabled();
  });

  it("有会话内容时，点击复制会话按钮可以将当前会话格式化并复制到剪贴板，显示已复制状态，2秒后恢复", async () => {
    mockStreamInterviewChat.mockImplementation(async ({ onDelta }) => {
      onDelta("请先介绍一个项目。");
    });

    render(<InterviewChat />);

    // 发送一条消息以产生会话
    await userEvent.type(screen.getByLabelText("输入面试练习内容"), "练分布式系统");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    // 等待消息流结束
    await waitFor(() => {
      expect(screen.getByText("请先介绍一个项目。")).toBeInTheDocument();
    });

    const copyButton = screen.getByRole("button", { name: /复制会话/i });
    expect(copyButton).not.toBeDisabled();

    // 点击复制
    await userEvent.click(copyButton);

    // 检查复制的内容是否符合预期
    expect(writeTextMock).toHaveBeenCalledWith(
      "【面试官】：你好！在开始之前，请告诉我你想练习的面试岗位、公司，或者你想练习的具体项目背景与技术主题？（例如：AI Agent 工程师，或者分布式系统的架构设计）\n\n【求职者】：练分布式系统\n\n【面试官】：请先介绍一个项目。"
    );

    // 检查状态更新为“已复制”
    await waitFor(() => {
      expect(screen.getByText("已复制")).toBeInTheDocument();
    });

    // 等待 2 秒后，变回“复制会话”
    await waitFor(() => {
      expect(screen.getByText("复制会话")).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it("初始渲染时显示 AI 开场引导消息，不为空白", () => {
    render(<InterviewChat />);
    expect(screen.getByText(/面试岗位/)).toBeInTheDocument();
  });

  it("closing 阶段显示「开始新一轮面试」按钮，输入框仍可使用", async () => {
    mockStreamInterviewChat.mockImplementation(async ({ onState }) => {
      onState?.({ stage: "closing", question_count: 5, total_questions: 5 });
    });

    render(<InterviewChat />);

    await userEvent.type(screen.getByLabelText("输入面试练习内容"), "最后一题");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "开始新一轮面试" })).toBeInTheDocument();
    });
    expect(screen.getByLabelText("输入面试练习内容")).not.toBeDisabled();
  });

  it("点击「开始新一轮面试」后，消息重置为开场消息，报告消失", async () => {
    mockStreamInterviewChat.mockImplementation(async ({ onState, onReport }) => {
      onState?.({ stage: "closing", question_count: 5, total_questions: 5 });
      onReport?.({
        overall_score: 7.5,
        technical_depth: 4.0,
        quantified_results: 3.0,
        failure_tradeoffs: 4.0,
        structure: 3.5,
        highlights: ["表达清晰"],
        improvements: ["可补充量化数据"],
      });
    });

    render(<InterviewChat />);

    await userEvent.type(screen.getByLabelText("输入面试练习内容"), "最后一题");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(screen.getByText("本轮面试报告")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "开始新一轮面试" }));

    await waitFor(() => {
      expect(screen.queryByText("本轮面试报告")).not.toBeInTheDocument();
    });
    expect(screen.getByText(/面试岗位/)).toBeInTheDocument();
  });

  it("收到 report 事件后，ReportCard 在聊天流末尾渲染", async () => {
    mockStreamInterviewChat.mockImplementation(async ({ onState, onReport, onDelta }) => {
      onState?.({ stage: "closing", question_count: 5, total_questions: 5 });
      onDelta("感谢参与本次面试。");
      onReport?.({
        overall_score: 8.0,
        technical_depth: 4.0,
        quantified_results: 4.0,
        failure_tradeoffs: 4.0,
        structure: 4.0,
        highlights: ["整体良好"],
        improvements: ["补充细节"],
      });
    });

    render(<InterviewChat />);

    await userEvent.type(screen.getByLabelText("输入面试练习内容"), "第五题");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(screen.getByText("本轮面试报告")).toBeInTheDocument();
    });
    expect(screen.getByText("8.0")).toBeInTheDocument();
    expect(screen.getByText("整体良好")).toBeInTheDocument();
  });

  it("输入法状态对回车发送的影响", async () => {
    mockStreamInterviewChat.mockImplementation(async () => {});

    render(<InterviewChat />);

    const input = screen.getByLabelText("输入面试练习内容");
    
    // 1. isComposing = true 时，回车不发送
    await userEvent.type(input, "输入中");
    fireEvent.compositionStart(input); // 显式设置 isComposingRef = true
    fireEvent.keyDown(input, {
      key: "Enter",
      code: "Enter",
    });
    
    // 等待以确保没有任何异步调用发生
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(mockStreamInterviewChat).not.toHaveBeenCalled();

    // 2. isComposing = false 时，回车正常发送
    fireEvent.compositionEnd(input);
    // 等待 setTimeout 0 清除状态
    await new Promise((resolve) => setTimeout(resolve, 10));

    fireEvent.keyDown(input, {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(mockStreamInterviewChat).toHaveBeenCalled();
    });
  });

  it("输入法合成结束瞬间的回车保护", async () => {
    mockStreamInterviewChat.mockImplementation(async () => {});

    render(<InterviewChat />);

    const input = screen.getByLabelText("输入面试练习内容");
    
    // 确保有输入内容，否则 handleSubmit 会直接返回
    await userEvent.type(input, "内容");
    
    // 1. 模拟合成开始
    fireEvent.compositionStart(input);
    
    // 2. 模拟合成结束，但在紧接着触发 Enter (模拟某些浏览器下 compositionEnd 先于 keydown 的情况)
    fireEvent.compositionEnd(input);
    
    // 此时 event.isComposing 为 false，但由于 setTimeout(..., 0)，isComposingRef 应该还在保护中
    fireEvent.keyDown(input, {
      key: "Enter",
      code: "Enter",
      isComposing: false,
      nativeEvent: { isComposing: false },
    });
    
    // 等待以确保没有任何发送调用发生
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(mockStreamInterviewChat).not.toHaveBeenCalled();
    
    // 3. 等待合成状态彻底清除（setTimeout 0 结束）
    await new Promise((resolve) => setTimeout(resolve, 10));
    
    // 4. 再次回车，此时应该可以正常发送
    fireEvent.keyDown(input, {
      key: "Enter",
      code: "Enter",
      isComposing: false,
      nativeEvent: { isComposing: false },
    });

    await waitFor(() => {
      expect(mockStreamInterviewChat).toHaveBeenCalled();
    });
  });

  it("从 sessionStorage 读取上下文后显示确认消息", () => {
    sessionStorage.setItem(
      "interview_context",
      JSON.stringify({ target_role: "前端工程师", user_background: "Vue 项目" }),
    );

    render(<InterviewChat />);

    expect(screen.getByText(/前端工程师/)).toBeInTheDocument();
    expect(sessionStorage.getItem("interview_context")).toBeNull();
  });

  it("没有 sessionStorage 上下文时显示通用开场白", () => {
    sessionStorage.removeItem("interview_context");

    render(<InterviewChat />);

    expect(screen.getByText(/面试岗位/)).toBeInTheDocument();
  });
});
