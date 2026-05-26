import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CoachDashboard } from "./coach-dashboard";

const mockPush = vi.hoisted(() => vi.fn());
const mockReplace = vi.hoisted(() => vi.fn());
const mockSearchParams = vi.hoisted(() => vi.fn(() => new URLSearchParams()));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  useSearchParams: () => mockSearchParams(),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: true,
    getToken: vi.fn().mockResolvedValue("test-token"),
  }),
}));

vi.mock("@/lib/interview-chat", () => ({
  fetchCoachOpeningMessage: vi.fn(),
  fetchInterviewContext: vi.fn(),
  fetchInterviewHistory: vi.fn().mockResolvedValue({ sessions: [] }),
  resetInterviewSession: vi.fn().mockResolvedValue(undefined),
  enterInterviewRoom: vi.fn(),
}));

vi.mock("@/lib/user", () => ({
  updateUserProfile: vi.fn().mockResolvedValue({}),
  fetchUserProfile: vi.fn().mockResolvedValue({}),
  fetchUserStories: vi.fn().mockResolvedValue([]),
}));

import {
  fetchCoachOpeningMessage,
  fetchInterviewContext,
  fetchInterviewHistory,
  resetInterviewSession,
  enterInterviewRoom,
} from "@/lib/interview-chat";
const mockFetchOpening = vi.mocked(fetchCoachOpeningMessage);
const mockFetch = vi.mocked(fetchInterviewContext);
const mockFetchHistory = vi.mocked(fetchInterviewHistory);
const mockResetInterviewSession = vi.mocked(resetInterviewSession);
const mockEnterInterviewRoom = vi.mocked(enterInterviewRoom);

describe("CoachDashboard", () => {
  beforeEach(() => {
    mockFetchOpening.mockReset();
    mockFetch.mockReset();
    mockFetchHistory.mockReset();
    mockPush.mockReset();
    mockReplace.mockReset();
    mockResetInterviewSession.mockClear();
    mockEnterInterviewRoom.mockReset();

    mockFetchHistory.mockResolvedValue({
      sessions: [
        { id: "1", date: "2026-05-20", topic: "分布式 · 高并发", target_role: "后端", score: 8.5, pass_fail: "pass", key_issues: [], report: { technical_depth: 4, quantified_results: 4, failure_tradeoffs: 4, structure: 4, key_concepts: ["缓存", "短链接"], highlights: [], improvements: [] } },
        { id: "2", date: "2026-05-19", topic: "分布式 · 消息队列", target_role: "后端", score: 8.0, pass_fail: "pass", key_issues: [], report: { technical_depth: 4, quantified_results: 4, failure_tradeoffs: 4, structure: 4, key_concepts: ["Kafka", "幂等性"], highlights: [], improvements: [] } },
        { id: "3", date: "2026-05-18", topic: "基础 · 数据库", target_role: "后端", score: 7.5, pass_fail: "partial", key_issues: [], report: { technical_depth: 3, quantified_results: 3, failure_tradeoffs: 3, structure: 3, key_concepts: ["MVCC", "索引"], highlights: [], improvements: [] } },
        { id: "4", date: "2026-05-17", topic: "基础 · 网络", target_role: "后端", score: 6.5, pass_fail: "fail", key_issues: [], report: { technical_depth: 2, quantified_results: 2, failure_tradeoffs: 2, structure: 2, key_concepts: ["TCP", "HTTPS"], highlights: [], improvements: [] } },
        { id: "5", date: "2026-05-16", topic: "架构 · 微服务", target_role: "后端", score: 8.2, pass_fail: "pass", key_issues: [], report: { technical_depth: 4, quantified_results: 4, failure_tradeoffs: 4, structure: 4, key_concepts: ["熔断", "降级"], highlights: [], improvements: [] } },
        { id: "6", date: "2026-05-15", topic: "架构 · 性能优化", target_role: "后端", score: 8.8, pass_fail: "pass", key_issues: [], report: { technical_depth: 5, quantified_results: 5, failure_tradeoffs: 5, structure: 5, key_concepts: ["LFU Cache", "零拷贝"], highlights: [], improvements: [] } },
      ]
    });
    mockFetchOpening.mockResolvedValue({
      greeting: "欢迎回来，今天继续练 AI Agent 面试。",
      weakness_summary: "你在结果量化方面不足，项目收益说得不够具体。",
      evidence: "这个短板在你过去 7 场面试中出现了 5 场。",
      focus_today: "今天重点练习用数据证明项目收益。",
      cta_type: "returning",
    });
  });

  it("加载期间显示骨架屏", () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // 永不 resolve
    render(<CoachDashboard />);
    expect(screen.getByTestId("coach-skeleton")).toBeInTheDocument();
  });

  it("老用户：显示「欢迎回来」并展示历史场次数", async () => {
    mockFetch.mockResolvedValue({
      is_returning: true,
      target_role: "AI Agent 工程师",
      work_years: null,
      target_company: null,
      user_background: "熟悉 LangChain",
      session_count: 7,
    });

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/欢迎回来，今天继续练 AI Agent 面试/)).toBeInTheDocument();
    });
    expect(screen.getByText(/结果量化方面不足/)).toBeInTheDocument();
    expect(screen.getByText(/这个短板在你过去/)).toBeInTheDocument();
    expect(
      screen.getAllByText("7 场").some((element) => element.className.includes("text-[#e11d48]")),
    ).toBe(true);
    expect(screen.getByText("5 场").className).toContain("text-[#e11d48]");
    expect(screen.queryByTestId("coach-skeleton")).not.toBeInTheDocument();
  });

  it("老用户：开场词接口慢时不阻塞页面展示，显示开场词骨架屏", async () => {
    mockFetchOpening.mockImplementation(() => new Promise(() => {}));
    mockFetch.mockResolvedValue({
      is_returning: true,
      target_role: "AI Agent 工程师",
      work_years: null,
      target_company: null,
      user_background: "熟悉 LangChain",
      session_count: 7,
    });

    render(<CoachDashboard />);

    // 页面主体渲染完成（header 场次可见）
    await waitFor(() => {
      expect(screen.getAllByText(/7 场/)[0]).toBeInTheDocument();
    });
    // 开场词未到时显示专用骨架屏，不展示旧 fallback 文案
    expect(screen.getByTestId("coach-opening-skeleton")).toBeInTheDocument();
    expect(screen.queryByText("欢迎回来。")).not.toBeInTheDocument();
    expect(screen.queryByTestId("coach-skeleton")).not.toBeInTheDocument();
  });

  it("老用户：Coach 首页只预览少量记忆，并提供查看全部入口", async () => {
    mockFetch.mockResolvedValue({
      is_returning: true,
      target_role: "AI Agent 工程师",
      work_years: null,
      target_company: null,
      user_background: "熟悉 LangChain",
      session_count: 7,
    });

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/欢迎回来，今天继续练 AI Agent 面试/)).toBeInTheDocument();
    });

    expect(screen.getByText("近期记忆")).toBeInTheDocument();
    expect(screen.getByText("显示 2 / 6")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看全部记忆" })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByText("缓存")).toBeInTheDocument();
    expect(screen.getByText("短链接")).toBeInTheDocument();
    expect(screen.queryByText(/LFU Cache/)).not.toBeInTheDocument();
  });

  it("老用户：开场诊断里的证据数字和短板关键词会高亮", async () => {
    mockFetchOpening.mockResolvedValue({
      greeting: "欢迎回到面试练习！我们将继续提升你的面试表现。",
      weakness_summary: "你在回答开放性问题时缺少具体例证，这使得你的论证不够有说服力。",
      evidence: "在你过去的六场面试中，回答开放性问题时多次缺乏具体实例，使得考官难以理解你的真实能力和经验。",
      focus_today: "今天重点练习针对开放性问题的回答，我们会针对你的经历找出具体例子，通过丰富的细节提升说服力。",
      cta_type: "returning",
    });
    mockFetch.mockResolvedValue({
      is_returning: true,
      target_role: "AI Agent 工程师",
      work_years: null,
      target_company: null,
      user_background: "熟悉 LangChain",
      session_count: 7,
    });

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/欢迎回到面试练习/)).toBeInTheDocument();
    });

    expect(screen.getByText("六场").className).toContain("text-[#e11d48]");
    expect(screen.getByText("缺少具体例证").className).toContain("text-[#e11d48]");
    expect(screen.getAllByText("开放性问题")[0].className).toContain("text-[#4f46e5]");
  });

  it("新用户：显示「你好，我还不认识你」和岗位选择按钮", async () => {
    mockFetchOpening.mockResolvedValue({
      greeting: "你好。我还不认识你。",
      weakness_summary: null,
      evidence: null,
      focus_today: "先选择一个目标岗位，我们从一场模拟面试开始。",
      cta_type: "new",
    });
    mockFetch.mockResolvedValue({
      is_returning: false,
      target_role: null,
      work_years: null,
      target_company: null,
      user_background: null,
      session_count: 0,
    });

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/还不认识你/)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "AI Agent 工程师" })).toBeInTheDocument();
  });

  it("API 失败时降级为新用户 UI", async () => {
    mockFetch.mockRejectedValue(new Error("网络错误"));
    mockFetchOpening.mockRejectedValue(new Error("网络错误"));

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/还不认识你/)).toBeInTheDocument();
    });
  });

  it("新用户选择岗位后点击直接试一场会进入面试房间", async () => {
    mockFetchOpening.mockResolvedValue({
      greeting: "你好。我还不认识你。",
      weakness_summary: null,
      evidence: null,
      focus_today: "先选择一个目标岗位，我们从一场模拟面试开始。",
      cta_type: "new",
    });
    mockFetch.mockResolvedValue({
      is_returning: false,
      target_role: null,
      work_years: null,
      target_company: null,
      user_background: null,
      session_count: 0,
    });

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/还不认识你/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "AI Agent 工程师" }));
    const directStartButton = await screen.findByRole(
      "button",
      { name: "我直接试一场吧" },
      { timeout: 2000 },
    );
    fireEvent.click(directStartButton);

    await waitFor(() => {
      expect(mockEnterInterviewRoom).toHaveBeenCalledWith(
        expect.objectContaining({
          context: {
            target_role: "AI Agent 工程师",
            user_background: "我在准备 AI Agent 工程师 的面试",
          },
        })
      );
    });
    expect(mockPush).not.toHaveBeenCalledWith("/settings");
  });

  describe("from=interview 软提示", () => {
    beforeEach(() => {
      mockReplace.mockClear();
      mockFetch.mockResolvedValue({
        is_returning: true,
        target_role: "AI Agent 工程师",
        work_years: null,
        target_company: null,
        user_background: "熟悉 LangChain",
        session_count: 7,
      });
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("URL 带 from=interview 时显示软提示并在 4 秒后消失", async () => {
      mockSearchParams.mockReturnValue(new URLSearchParams("from=interview"));
      vi.useFakeTimers();

      render(<CoachDashboard />);

      // 推进 100ms 等待 API 加载的异步 Promise 及状态更新跑完
      await vi.advanceTimersByTimeAsync(100);

      expect(screen.getByText(/先在这里告诉我练什么/)).toBeInTheDocument();
      expect(mockReplace).toHaveBeenCalledWith("/coach"); // 立即清 query

      // 快进 4000ms 触发定时器隐藏软提示
      await vi.advanceTimersByTimeAsync(4000);

      expect(screen.queryByText(/先在这里告诉我练什么/)).not.toBeInTheDocument();

      vi.useRealTimers();
    });

    it("URL 不带 from=interview 时不显示软提示", () => {
      mockSearchParams.mockReturnValue(new URLSearchParams(""));

      render(<CoachDashboard />);

      expect(screen.queryByText(/先在这里告诉我练什么/)).not.toBeInTheDocument();
      expect(mockReplace).not.toHaveBeenCalledWith("/coach");
    });
  });

  describe("CoachOpeningCopy 记忆 hints 槽", () => {
    it("long_memory_hints 有内容时渲染", async () => {
      mockFetch.mockResolvedValue({
        is_returning: true,
        target_role: "AI Agent 工程师",
        work_years: null,
        target_company: null,
        user_background: "熟悉 LangChain",
        session_count: 7,
      });
      mockFetchOpening.mockResolvedValue({
        greeting: "hi",
        weakness_summary: null,
        evidence: null,
        focus_today: "练 X",
        cta_type: "new",
        long_memory_hints: ["上次你说过偏好用 RAG"],
        hobby_hints: ["你喜欢分布式系统"],
      });

      render(<CoachDashboard />);

      await waitFor(() => {
        expect(screen.getByText(/上次你说过偏好用 RAG/)).toBeInTheDocument();
      });
      expect(screen.getByText(/你喜欢分布式系统/)).toBeInTheDocument();
    });

    it("hints 为空/缺失时不渲染槽", async () => {
      mockFetch.mockResolvedValue({
        is_returning: true,
        target_role: "AI Agent 工程师",
        work_years: null,
        target_company: null,
        user_background: "熟悉 LangChain",
        session_count: 7,
      });
      mockFetchOpening.mockResolvedValue({
        greeting: "hi",
        weakness_summary: null,
        evidence: null,
        focus_today: "练 X",
        cta_type: "new",
      });

      render(<CoachDashboard />);

      await waitFor(() => {
        expect(screen.getByText("hi")).toBeInTheDocument();
      });
      expect(screen.queryByTestId("coach-long-memory-hints")).not.toBeInTheDocument();
      expect(screen.queryByTestId("coach-hobby-hints")).not.toBeInTheDocument();
    });
  });
});
