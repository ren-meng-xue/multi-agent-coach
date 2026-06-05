import { beforeEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  within,
} from "@testing-library/react";

if (typeof globalThis.crypto === "undefined") {
  (globalThis as any).crypto = {};
}
if (typeof globalThis.crypto.randomUUID === "undefined") {
  globalThis.crypto.randomUUID = () => "test-uuid-12345678" as any;
}
import userEvent from "@testing-library/user-event";
import { InterviewChat } from "./interview-chat";
import {
  resumePrepareStreamFetch,
  startPrepareAndLaunchStreamFetch,
  startPrepareStreamFetch,
  streamInterviewChat,
} from "@/lib/interview-chat";
import { useAuth } from "@clerk/nextjs";

const mockUseAuth = vi.fn().mockReturnValue({
  isLoaded: true,
  isSignedIn: true,
  getToken: vi.fn().mockResolvedValue("test-token"),
});

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn(), replace: vi.fn() })),
  useSearchParams: vi.fn(() => new URLSearchParams()),
  usePathname: vi.fn(() => "/interview"),
}));

import { useRouter } from "next/navigation";

vi.mock("@/lib/interview-chat", () => ({
  streamInterviewChat: vi.fn(),
  resetInterviewSession: vi.fn().mockResolvedValue(undefined),
  startPrepareStreamFetch: vi.fn(),
  startPrepareAndLaunchStreamFetch: vi.fn(),
  resumePrepareStreamFetch: vi.fn(),
  fetchActiveInterviewSession: vi.fn().mockResolvedValue({}),
  fetchInterviewContext: vi.fn().mockResolvedValue({
    is_returning: false,
    target_role: null,
    target_company: null,
    user_background: null,
    session_count: 0,
    last_session_id: null,
    resume_filename: "resume.pdf",
  }),
  isTextMessage: (message: { role: string }) =>
    message.role === "user" || message.role === "assistant",
  isPrepareTraceMessage: (message: { role: string; kind?: string }) =>
    message.role === "trace" && message.kind === "prepare",
  isTurnTraceMessage: (message: { role: string; kind?: string }) =>
    message.role === "trace" && message.kind === "turn",
  formatTraceTokens: (id: string, tokens: string) => tokens,
  INTERVIEW_NODE_TITLES: {},
  INTERVIEW_NODE_LABELS: {},
  PREPARE_NODE_TITLES: {},
}));

import { fetchActiveInterviewSession } from "@/lib/interview-chat";
import { aggregateReactSteps } from "./interview-chat";

const mockStreamInterviewChat = vi.mocked(streamInterviewChat);
const mockStartPrepareStreamFetch = vi.mocked(startPrepareStreamFetch);
const mockStartPrepareAndLaunchStreamFetch = vi.mocked(
  startPrepareAndLaunchStreamFetch,
);
const mockResumePrepareStreamFetch = vi.mocked(resumePrepareStreamFetch);
const mockFetchActiveSession = vi.mocked(fetchActiveInterviewSession);

describe("aggregateReactSteps", () => {
  it("creates a new iteration when tool_thinking_start arrives", () => {
    const steps = aggregateReactSteps([], {
      event: "tool_thinking_start",
      data: { iteration: 0, step_id: "think-0" },
    });
    expect(steps).toHaveLength(1);
    expect(steps[0]).toMatchObject({
      index: 0,
      thinkStatus: "running",
      toolCalls: [],
    });
  });

  it("appends streamed think tokens to thinkContent", () => {
    let steps = aggregateReactSteps([], {
      event: "tool_thinking_start",
      data: { iteration: 0, step_id: "think-0" },
    });
    steps = aggregateReactSteps(steps, {
      event: "tool_thinking_token",
      data: { iteration: 0, step_id: "think-0", text: "我先" },
    });
    steps = aggregateReactSteps(steps, {
      event: "tool_thinking_token",
      data: { iteration: 0, step_id: "think-0", text: "调研" },
    });
    expect(steps[0].thinkContent).toBe("我先调研");
  });

  it("adds a running tool_call_start card and updates on tool_call_done", () => {
    let steps = aggregateReactSteps([], {
      event: "tool_thinking_start",
      data: { iteration: 0, step_id: "think-0" },
    });
    steps = aggregateReactSteps(steps, {
      event: "tool_call_start",
      data: {
        iteration: 0,
        step_id: "tool-0-c1",
        tool_name: "extract_jd_text",
        tool_args_summary: 'text="..."',
      },
    });
    expect(steps[0].toolCalls).toHaveLength(1);
    expect(steps[0].toolCalls[0].status).toBe("running");

    steps = aggregateReactSteps(steps, {
      event: "tool_call_done",
      data: {
        iteration: 0,
        step_id: "tool-0-c1",
        tool_result_summary: "{title, company}",
        tool_elapsed_ms: 1200,
      },
    });
    expect(steps[0].toolCalls[0].status).toBe("done");
    expect(steps[0].toolCalls[0].elapsedMs).toBe(1200);
    expect(steps[0].toolCalls[0].resultSummary).toBe("{title, company}");
  });

  it("marks tool call as error when tool_error is present", () => {
    let steps = aggregateReactSteps([], {
      event: "tool_thinking_start",
      data: { iteration: 0, step_id: "think-0" },
    });
    steps = aggregateReactSteps(steps, {
      event: "tool_call_start",
      data: {
        iteration: 0,
        step_id: "tool-0-c1",
        tool_name: "web_search",
        tool_args_summary: "",
      },
    });
    steps = aggregateReactSteps(steps, {
      event: "tool_call_done",
      data: {
        iteration: 0,
        step_id: "tool-0-c1",
        tool_error: "Tavily timeout",
        tool_elapsed_ms: 30000,
      },
    });
    expect(steps[0].toolCalls[0].status).toBe("error");
    expect(steps[0].toolCalls[0].error).toBe("Tavily timeout");
  });
});

describe("InterviewChat", () => {
  let writeTextMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useRealTimers();
    mockStreamInterviewChat.mockReset();
    mockStartPrepareStreamFetch.mockReset();
    mockStartPrepareAndLaunchStreamFetch.mockReset();
    mockResumePrepareStreamFetch.mockReset();
    mockFetchActiveSession.mockReset();
    writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: writeTextMock,
      },
      configurable: true,
      writable: true,
    });
  });

  function mockPrepareDone() {
    mockStartPrepareStreamFetch.mockImplementation(async function* () {
      yield {
        event: "done",
        data: {
          prepared_questions: [
            {
              id: 1,
              question: "请解释 CAP 定理在你的项目中如何取舍。",
              category: "system_design",
              focus_area: "CAP",
              priority: 1,
            },
          ],
          summary: "测试综合评估摘要",
          direction: "分布式系统",
        },
      };
    });
  }

  async function startPreparedInterview() {
    await userEvent.type(
      screen.getByLabelText("输入面试练习内容"),
      "练分布式系统",
    );
    await userEvent.click(screen.getByRole("button", { name: "发送" }));
    // 面试现在是自动开始的
    await waitFor(
      () => {
        expect(mockStreamInterviewChat).toHaveBeenCalled();
      },
      { timeout: 3000 },
    );
  }

  it("输入栏固定在聊天面板底部，长内容只滚动消息区", () => {
    render(<InterviewChat />);

    const form = screen.getByRole("form", { name: "面试输入栏" });
    expect(form).toHaveClass("sticky", "bottom-0", "shrink-0");
  });

  it("输入框不展示浏览器历史输入记录", () => {
    render(<InterviewChat />);

    expect(screen.getByLabelText("输入面试练习内容")).toHaveAttribute(
      "autocomplete",
      "off",
    );
  });

  it("opening 阶段发送方向后启动多 Agent 准备流，而不是直接进入普通聊天", async () => {
    mockStartPrepareStreamFetch.mockImplementation(async function* () {
      yield { event: "node_start", data: { node: "master", label: "MASTER" } };
      yield {
        event: "node_token",
        data: { node: "master", text: "• 识别练习方向：分布式系统\n" },
      };
      yield {
        event: "node_done",
        data: {
          node: "master",
          elapsed_ms: 10,
          chain: ["question_gen"],
          need_direction: false,
        },
      };
      yield {
        event: "done",
        data: {
          prepared_questions: [
            {
              id: 1,
              question: "请解释 CAP 定理在你的项目中如何取舍。",
              category: "system_design",
              focus_area: "CAP",
              priority: 1,
            },
          ],
          summary: "根据分布式系统方向生成了 1 道题。",
          direction: "分布式系统",
        },
      };
    });

    render(<InterviewChat />);

    await userEvent.type(
      screen.getByLabelText("输入面试练习内容"),
      "练分布式系统",
    );
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    expect(screen.getByText("练分布式系统")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText(/准备就绪/).length).toBeGreaterThan(0);
    });
    expect(mockStartPrepareStreamFetch).toHaveBeenCalledWith(
      expect.objectContaining({
        token: "test-token",
        userDirection: "练分布式系统",
      }),
    );
    expect(mockStreamInterviewChat).not.toHaveBeenCalled();
    expect(screen.getByText("调度中心：准备就绪")).toBeInTheDocument();
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
    mockPrepareDone();
    mockStreamInterviewChat.mockImplementation(async ({ onDelta }) => {
      onDelta("请");
      onDelta("详细");
      onDelta("描述");
      await new Promise<void>((resolve) => {
        resolveStream = resolve;
      });
    });

    render(<InterviewChat />);

    await startPreparedInterview();

    await waitFor(() =>
      expect(requestAnimationFrameSpy).toHaveBeenCalledTimes(1),
    );
    expect(screen.queryByText("请详细描述")).not.toBeInTheDocument();

    await act(async () => {
      pendingFrame?.(performance.now());
    });

    expect(screen.getByText("请详细描述")).toBeInTheDocument();

    await act(async () => {
      resolveStream();
    });
  });

  it("首题启动失败后隐藏准备卡和内部开始动作，只保留紧凑错误行并恢复输入", async () => {
    mockPrepareDone();
    mockStreamInterviewChat.mockRejectedValue(new Error("AI 暂时无法响应"));

    render(<InterviewChat />);

    const input = screen.getByLabelText("输入面试练习内容");
    await startPreparedInterview();

    await waitFor(() => {
      expect(screen.getByText("AI 暂时无法响应")).toBeInTheDocument();
    });
    expect(screen.queryByText("准备完成")).not.toBeInTheDocument();
    expect(input).not.toBeDisabled();
  });

  it("初始渲染时没有会话内容，复制按钮禁用", () => {
    render(<InterviewChat />);
    const copyButton = screen.getByRole("button", { name: /复制会话/i });
    expect(copyButton).toBeDisabled();
  });

  it("有会话内容时，点击复制会话按钮可以将当前会话格式化并复制到剪贴板，显示已复制状态，2秒后恢复", async () => {
    mockStartPrepareStreamFetch.mockImplementation(async function* () {
      yield {
        event: "done",
        data: {
          prepared_questions: [],
          summary: "准备完成",
          direction: "分布式系统",
        },
      };
    });
    mockStreamInterviewChat.mockImplementation(async ({ onDelta }) => {
      onDelta("请先介绍一个项目。");
    });

    render(<InterviewChat />);

    // 发送一条消息以产生会话
    await userEvent.type(
      screen.getByLabelText("输入面试练习内容"),
      "练分布式系统",
    );
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(screen.getAllByText(/准备就绪/).length).toBeGreaterThan(0);
    });

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
      "【求职者】：练分布式系统\n\n【面试官】：请先介绍一个项目。",
    );

    // 检查状态更新为“已复制”
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "已复制" }),
      ).toBeInTheDocument();
    });

    // 等待 2 秒后，变回“复制会话”
    await waitFor(
      () => {
        expect(
          screen.getByRole("button", { name: "复制会话" }),
        ).toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });

  it("点击复制完整记录按钮可以将当前会话（含 AI 思考过程）格式化并复制到剪贴板", async () => {
    mockStartPrepareStreamFetch.mockImplementation(async function* () {
      yield {
        event: "node_start",
        data: { node: "master", label: "MASTER" },
      };
      yield {
        event: "node_token",
        data: { node: "master", text: "正在为您定制题目" },
      };
      yield {
        event: "node_done",
        data: { node: "master" },
      };
      yield {
        event: "node_start",
        data: { node: "question_gen", label: "出题专家" },
      };
      yield {
        event: "node_token",
        data: {
          node: "question_gen",
          text: '{"question": "什么是分布式锁？"}',
        },
      };
      yield {
        event: "node_done",
        data: { node: "question_gen" },
      };
      yield {
        event: "done",
        data: {
          prepared_questions: [],
          summary: "准备完成",
          direction: "分布式",
        },
      };
    });

    render(<InterviewChat />);

    // 发送消息
    await userEvent.type(screen.getByLabelText("输入面试练习内容"), "练分布式");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(screen.getAllByText(/准备就绪/).length).toBeGreaterThan(0);
    });

    // 面试现在是自动开始的，不再需要手动点击“开始本轮面试”按钮
    await waitFor(
      () => {
        expect(mockStreamInterviewChat).toHaveBeenCalled();
      },
      { timeout: 3000 },
    );

    const fullCopyButton = screen.getByRole("button", {
      name: /复制完整记录/i,
    });
    expect(fullCopyButton).not.toBeDisabled();

    // 模拟一个 Turn Trace 以测试评分和标签
    await act(async () => {
      mockStreamInterviewChat.mock.calls[0]?.[0].onTraceNode?.({
        phase: "start",
        node: "evaluator",
        label: "评估官",
      });
      mockStreamInterviewChat.mock.calls[0]?.[0].onTraceNode?.({
        phase: "done",
        node: "evaluator",
        summaryScore: 9.2,
        candidateLevel: "senior",
        latentSignals: ["架构思维强"],
      });
    });

    // 等待 UI 更新显示卡片，并展开
    await waitFor(() => {
      expect(screen.getByText(/查看 AI 思考过程/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/查看 AI 思考过程/));

    await waitFor(() => {
      expect(screen.getByTestId("trace-node-evaluator")).toBeInTheDocument();
    });

    // 点击复制
    await userEvent.click(fullCopyButton);

    // 检查复制的内容是否包含所有结构化数据
    const clipboardText =
      writeTextMock.mock.calls[writeTextMock.mock.calls.length - 1][0];
    expect(clipboardText).toContain("【AI 思考过程 - 准备阶段】：");
    expect(clipboardText).toContain("什么是分布式锁？");
    expect(clipboardText).toContain("[级别: senior]");
    expect(clipboardText).toContain("[信号: 架构思维强]");
    expect(clipboardText).toContain("【求职者】：练分布式");

    // 检查状态更新
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "已复制" }),
      ).toBeInTheDocument();
    });
  });

  it("初始渲染时不显示无目标岗位开场卡片", () => {
    render(<InterviewChat />);
    expect(screen.queryByText(/目标岗位/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("输入面试练习内容")).toBeInTheDocument();
  });

  it("closing 阶段显示「开启下一场模拟面试」按钮，输入框仍可使用", async () => {
    mockPrepareDone();
    mockStreamInterviewChat.mockImplementation(
      async ({ onState, onReport }) => {
        onState?.({ stage: "closing", question_count: 5, total_questions: 5 });
        onReport?.({
          overall_score: 8.0,
          technical_depth: 4.0,
          quantified_results: 4.0,
          failure_tradeoffs: 4.0,
          structure: 4.0,
          highlights: ["Good"],
          improvements: ["Better"],
        });
      },
    );

    render(<InterviewChat />);

    await startPreparedInterview();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "开启下一场模拟面试" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByLabelText("输入面试练习内容")).not.toBeDisabled();
  });

  it("点击「开启下一场模拟面试」后，消息清空，报告消失", async () => {
    mockPrepareDone();
    mockStreamInterviewChat.mockImplementation(
      async ({ onState, onReport }) => {
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
      },
    );

    render(<InterviewChat />);

    await startPreparedInterview();

    await waitFor(() => {
      expect(screen.getByText("本轮面试报告")).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "开启下一场模拟面试" }),
    );

    await waitFor(() => {
      expect(screen.queryByText("本轮面试报告")).not.toBeInTheDocument();
    });
    expect(screen.queryByText(/目标岗位/)).not.toBeInTheDocument();
  });

  it("收到 report 事件后，ReportCard 在聊天流末尾渲染", async () => {
    mockPrepareDone();
    mockStreamInterviewChat.mockImplementation(
      async ({ onState, onReport, onDelta }) => {
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
      },
    );

    render(<InterviewChat />);

    await startPreparedInterview();

    await waitFor(() => {
      expect(screen.getByText("本轮面试报告")).toBeInTheDocument();
    });
    expect(screen.getByText("8.0")).toBeInTheDocument();
    expect(screen.getByText("整体良好")).toBeInTheDocument();
  });

  it("输入法状态对回车发送的影响", async () => {
    mockPrepareDone();

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
    expect(mockStartPrepareStreamFetch).not.toHaveBeenCalled();

    // 2. isComposing = false 时，回车正常发送
    fireEvent.compositionEnd(input);
    // 等待 setTimeout 0 清除状态
    await new Promise((resolve) => setTimeout(resolve, 10));

    fireEvent.keyDown(input, {
      key: "Enter",
      code: "Enter",
    });

    await waitFor(() => {
      expect(mockStartPrepareStreamFetch).toHaveBeenCalled();
    });
  });

  it("输入法合成结束瞬间的回车保护", async () => {
    mockPrepareDone();

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
    expect(mockStartPrepareStreamFetch).not.toHaveBeenCalled();

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
      expect(mockStartPrepareStreamFetch).toHaveBeenCalled();
    });
  });

  it("从 sessionStorage 读取上下文后，messages 初始化为空（走准备流水线）", () => {
    sessionStorage.setItem(
      "interview_context",
      JSON.stringify({
        target_role: "前端工程师",
        user_background: "Vue 项目",
      }),
    );

    render(<InterviewChat />);

    // Phase 3: 有 target_role 时走多 Agent 准备流，首屏消息为空，不显示旧的开场消息
    expect(screen.queryByText(/今天练/)).not.toBeInTheDocument();
    // 通用开场白也不显示（由 PreparationCard 接管）
    expect(screen.queryByText(/目标岗位/)).not.toBeInTheDocument();
  });

  it("准备流水线失败时回退到带岗位上下文的开场消息，不留下空白页", async () => {
    sessionStorage.setItem(
      "interview_context",
      JSON.stringify({
        target_role: "AI Agent 工程师",
        user_background: "LangGraph 项目",
      }),
    );
    mockStartPrepareStreamFetch.mockImplementation(async function* () {
      throw new Error("prepare failed");
    });

    render(<InterviewChat />);

    await waitFor(() => {
      expect(screen.getByText(/今天练/)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/AI Agent 工程师/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("输入面试练习内容")).not.toBeDisabled();
  });

  it("autoLaunch 进入 need_direction 后，resume 完成会兜底启动首题", async () => {
    sessionStorage.setItem(
      "interview_context",
      JSON.stringify({
        target_role: "AI Agent 工程师",
      }),
    );
    mockStartPrepareAndLaunchStreamFetch.mockImplementation(async function* () {
      yield {
        event: "node_start",
        data: { node: "supervisor", label: "调度" },
      };
      yield {
        event: "node_done",
        data: {
          node: "supervisor",
          elapsed_ms: 10,
          need_direction: true,
        },
      };
    });
    mockResumePrepareStreamFetch.mockImplementation(async function* () {
      yield {
        event: "done",
        data: {
          prepared_questions: [
            {
              id: 1,
              question: "请介绍一个 Agent 项目。",
              category: "behavioral",
              focus_area: "agent",
              priority: 1,
            },
          ],
          summary: "已生成首题",
          direction: "AI Agent 工程师",
        },
      };
    });
    mockStreamInterviewChat.mockImplementation(async ({ onDelta }) => {
      onDelta("第一题：请介绍一个 Agent 项目。");
    });

    render(<InterviewChat />);

    await waitFor(() => {
      expect(screen.getByText(/请告诉我你想练习什么岗位/)).toBeInTheDocument();
    });

    await userEvent.type(
      screen.getByLabelText("输入面试练习内容"),
      "AI Agent 工程师",
    );
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(
      () => {
        expect(mockStreamInterviewChat).toHaveBeenCalledWith(
          expect.objectContaining({
            message: "__START__",
          }),
        );
      },
      { timeout: 3000 },
    );
    expect(
      screen.getByText(/第一题：请介绍一个 Agent 项目/),
    ).toBeInTheDocument();
  });

  it("没有 sessionStorage 上下文时不显示通用开场白", () => {
    sessionStorage.removeItem("interview_context");

    render(<InterviewChat />);

    expect(screen.queryByText(/目标岗位/)).not.toBeInTheDocument();
  });

  it("在用户发送回答后，渲染 TurnTraceCard，并通过 onTraceNode 事件更新卡片状态与评分", async () => {
    sessionStorage.removeItem("interview_context");
    mockPrepareDone();

    let round = 0;
    mockStreamInterviewChat.mockImplementation(async (options) => {
      const { onTraceNode, onDelta, onState } = options;

      // 等待 10ms，让 React 先把 handleStartFirstQuestion 或 handleSend 产生的消息渲染上屏
      await new Promise((resolve) => setTimeout(resolve, 10));

      if (round === 0) {
        // 第一轮：首题出题（__START__）
        onTraceNode?.({ phase: "start", node: "master", label: "MASTER" });
        onTraceNode?.({
          phase: "done",
          node: "master",
          elapsedMs: 30,
          chain: ["ask_question"],
        });

        onTraceNode?.({
          phase: "start",
          node: "ask_question",
          label: "面试官 · 出题",
        });
        onDelta?.("分布式系统的核心难题是什么？");
        onTraceNode?.({ phase: "done", node: "ask_question", elapsedMs: 300 });

        onState?.({
          stage: "interview",
          question_count: 1,
          total_questions: 5,
        });
        round++;
      } else {
        // 第二轮：答题分析 + evaluator + followup
        onTraceNode?.({ phase: "start", node: "master", label: "MASTER" });
        onTraceNode?.({
          phase: "token",
          node: "master",
          text: "正在分析候选人回答",
        });
        onTraceNode?.({
          phase: "done",
          node: "master",
          elapsedMs: 50,
          chain: ["evaluator", "followup"],
        });

        // 再等待 10ms
        await new Promise((resolve) => setTimeout(resolve, 10));

        onTraceNode?.({ phase: "start", node: "evaluator", label: "评估" });
        onTraceNode?.({
          phase: "done",
          node: "evaluator",
          elapsedMs: 150,
          summaryScore: 8.5,
        });

        // 再等待 10ms
        await new Promise((resolve) => setTimeout(resolve, 10));

        onTraceNode?.({
          phase: "start",
          node: "followup",
          label: "面试官 · 追问",
        });
        onDelta?.("你提到的 RAG 是如何调优的？");
        onTraceNode?.({ phase: "done", node: "followup", elapsedMs: 500 });

        onState?.({
          stage: "interview",
          question_count: 2,
          total_questions: 5,
        });
      }
    });

    render(<InterviewChat />);

    await startPreparedInterview();

    await waitFor(() => {
      expect(screen.getByText(/分布式系统的核心难题/)).toBeInTheDocument();
    });

    const input = screen.getByLabelText("输入面试练习内容");
    await userEvent.type(input, "我是这么做 RAG 的");
    await userEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(screen.getAllByText(/多 Agent · 分析完成/).length).toBeGreaterThan(
        0,
      );
      expect(screen.getByText(/你提到的 RAG 是如何调优的/)).toBeInTheDocument();
    });
  });

  describe("HeroQuestionCard", () => {
    it("non-opening turn done 且 designedQuestion 有值时渲染 HeroQuestionCard", async () => {
      mockPrepareDone();

      let callCount = 0;
      mockStreamInterviewChat.mockImplementation(
        async ({ onTraceNode, onDelta, onState }: any) => {
          callCount++;
          if (callCount === 1) {
            // 开场轮：不含 designedQuestion
            onDelta?.("请介绍你的后端项目经验");
            onState?.({
              stage: "interview",
              question_count: 1,
              total_questions: 5,
            });
          } else {
            // 第二轮：含 designedQuestion + followupFocus（追问场景）
            onTraceNode?.({
              phase: "start",
              node: "ask_question",
              label: "追问",
            });
            onTraceNode?.({
              phase: "done",
              node: "ask_question",
              elapsedMs: 50,
              designedQuestion: "能具体说说你遇到的分布式锁问题吗？",
              designedCategory: "technical",
              followupFocus: "分布式锁",
            });
            onDelta?.("能具体说说分布式锁吗？");
            onState?.({
              stage: "interview",
              question_count: 2,
              total_questions: 5,
            });
          }
        },
      );

      render(<InterviewChat />);
      await startPreparedInterview();

      await waitFor(
        () => {
          expect(
            screen.getByText(/请介绍你的后端项目经验/),
          ).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      const input = screen.getByLabelText("输入面试练习内容");
      await userEvent.type(input, "我做了一个分布式系统");
      await userEvent.click(screen.getByRole("button", { name: "发送" }));

      await waitFor(
        () => {
          expect(screen.getByText(/📝 面试官追问/)).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
      expect(
        screen.getByText("能具体说说你遇到的分布式锁问题吗？"),
      ).toBeInTheDocument();
      // followupFocus 存在时 badge 显示"追问"
      const heroTitle = screen.getByText(/📝 面试官追问/);
      expect(within(heroTitle).getByText("追问")).toBeInTheDocument();
    });

    it("isOpening=true 时即使有 designedQuestion 也不渲染 HeroQuestionCard", async () => {
      mockPrepareDone();

      mockStreamInterviewChat.mockImplementation(
        async ({ onTraceNode, onDelta }: any) => {
          // 开场轮：带 designedQuestion，但 isOpening=true 所以不应渲染 HeroQuestionCard
          onTraceNode?.({
            phase: "start",
            node: "ask_question",
            label: "出题",
          });
          onTraceNode?.({
            phase: "done",
            node: "ask_question",
            elapsedMs: 50,
            designedQuestion: "请介绍你的技术栈",
            designedCategory: "technical",
          });
          onDelta?.("请介绍你的技术栈");
        },
      );

      render(<InterviewChat />);
      await startPreparedInterview();

      await waitFor(
        () => {
          expect(screen.getByText(/请介绍你的技术栈/)).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      // isOpening=true 时 HeroQuestionCard 不渲染
      expect(screen.queryByText(/📝 面试官追问/)).toBeNull();
    });
  });

  describe("路由守卫与加载异常", () => {
    beforeEach(() => {
      sessionStorage.clear();
      sessionStorage.setItem("test_routing_guard", "true");
    });

    it("无 sessionStorage context 且 /interview/active 返回空时，重定向到 /coach?from=interview", async () => {
      mockFetchActiveSession.mockResolvedValue({} as any);
      const replace = vi.fn();
      vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

      render(<InterviewChat />);
      await waitFor(() => {
        expect(replace).toHaveBeenCalledWith("/coach?from=interview");
      });
    });

    it("有 sessionStorage context 时不重定向，触发 prepare", async () => {
      sessionStorage.setItem(
        "interview_context",
        JSON.stringify({ target_role: "AI Agent 工程师" }),
      );
      mockFetchActiveSession.mockResolvedValue({} as any);
      const replace = vi.fn();
      vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

      render(<InterviewChat />);
      await new Promise((r) => setTimeout(r, 50));
      expect(replace).not.toHaveBeenCalled();
    });

    it("/interview/active 返回 in_progress 会话时不重定向，恢复消息", async () => {
      mockFetchActiveSession.mockResolvedValue({
        session_id: "abc",
        stage: "interview",
        question_count: 2,
        messages: [
          { role: "assistant", content: "已开始的面试" },
          { role: "user", content: "我的回答" },
        ],
      } as any);
      const replace = vi.fn();
      vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

      render(<InterviewChat />);
      await waitFor(() => {
        expect(screen.getByText("已开始的面试")).toBeInTheDocument();
      });
      expect(replace).not.toHaveBeenCalled();
    });

    it("/interview/active 返回 prepare_trace 时在首题前恢复准备面板", async () => {
      mockFetchActiveSession.mockResolvedValue({
        session_id: "abc",
        stage: "interview",
        question_count: 1,
        prepare_trace: {
          status: "done",
          nodes: [
            {
              id: "master",
              label: "MASTER",
              title: "识别方向，启动准备",
              status: "done",
              tokens: "• 用户目标是Senior Developer岗位。\n",
            },
          ],
          questions: [],
          summary: "",
          direction: "Senior Developer",
        },
        messages: [{ role: "assistant", content: "第一题：请介绍项目" }],
      } as any);
      const replace = vi.fn();
      vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

      render(<InterviewChat />);

      await waitFor(() => {
        expect(screen.getByText("调度中心：准备就绪")).toBeInTheDocument();
      });
      expect(screen.getByText("调度")).toBeInTheDocument();
      expect(
        screen.getByText("用户目标是Senior Developer岗位。"),
      ).toBeInTheDocument();
      expect(screen.getByText("第一题：请介绍项目")).toBeInTheDocument();
      expect(replace).not.toHaveBeenCalled();
    });

    it("/interview/active 返回 opening 空会话时启动准备流水线，而不是静态开场", async () => {
      mockFetchActiveSession.mockResolvedValue({
        session_id: "abc",
        target_role: "WEB前端工程师",
        stage: "opening",
        question_count: 0,
        total_questions: 5,
        messages: [],
      } as any);
      mockStartPrepareAndLaunchStreamFetch.mockImplementation(
        async function* () {
          yield {
            event: "node_start",
            data: { node: "master", label: "MASTER" },
          };
        },
      );
      const replace = vi.fn();
      vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

      render(<InterviewChat />);

      await waitFor(() => {
        expect(mockStartPrepareAndLaunchStreamFetch).toHaveBeenCalledWith(
          expect.objectContaining({
            token: "test-token",
            userDirection: "WEB前端工程师",
          }),
        );
      });
      expect(screen.queryByText(/今天练/)).not.toBeInTheDocument();
      expect(replace).not.toHaveBeenCalled();
    });

    it("/interview/active 抛错时不重定向，渲染兜底错误 UI", async () => {
      mockFetchActiveSession.mockRejectedValue(new Error("network"));
      const replace = vi.fn();
      vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

      render(<InterviewChat />);
      await waitFor(() => {
        expect(screen.getByText(/连接异常/)).toBeInTheDocument();
      });
      expect(replace).not.toHaveBeenCalled();
    });
  });
});
