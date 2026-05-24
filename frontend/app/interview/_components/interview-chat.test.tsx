import { beforeEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import { render, screen, waitFor } from "@testing-library/react";
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
}));

const mockStreamInterviewChat = vi.mocked(streamInterviewChat);

describe("InterviewChat", () => {
  beforeEach(() => {
    vi.useRealTimers();
    mockStreamInterviewChat.mockReset();
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
    mockStreamInterviewChat.mockImplementation(async ({ onDelta }) => {
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
        messages: expect.arrayContaining([{ role: "user", content: "练分布式系统" }]),
      }),
    );
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
});
