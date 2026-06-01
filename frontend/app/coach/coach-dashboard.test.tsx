import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
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

vi.mock("@/lib/coach", () => ({
  fetchUserStage: vi.fn().mockResolvedValue("prepare"),
  fetchLatestCoachPlan: vi.fn().mockResolvedValue(null),
}));

vi.mock("@/lib/user", () => ({
  fetchUserProfile: vi.fn().mockResolvedValue({}),
  fetchUserStories: vi.fn().mockResolvedValue([]),
}));

import {
  fetchCoachOpeningMessage,
  fetchInterviewContext,
  fetchInterviewHistory,
  enterInterviewRoom,
} from "@/lib/interview-chat";
import { fetchUserStage, fetchLatestCoachPlan } from "@/lib/coach";

const mockFetchOpening = vi.mocked(fetchCoachOpeningMessage);
const mockFetch = vi.mocked(fetchInterviewContext);
const mockFetchHistory = vi.mocked(fetchInterviewHistory);
const mockEnterInterviewRoom = vi.mocked(enterInterviewRoom);
const mockFetchUserStage = vi.mocked(fetchUserStage);
const mockFetchLatestCoachPlan = vi.mocked(fetchLatestCoachPlan);

describe("CoachDashboard", () => {
  beforeEach(() => {
    mockFetchOpening.mockReset();
    mockFetch.mockReset();
    mockFetchHistory.mockReset();
    mockPush.mockReset();
    mockReplace.mockReset();
    mockEnterInterviewRoom.mockReset();
    mockFetchUserStage.mockReset();
    mockFetchLatestCoachPlan.mockReset();

    mockFetchUserStage.mockResolvedValue("prepare");
    mockFetchLatestCoachPlan.mockResolvedValue(null);
    mockFetchHistory.mockResolvedValue({
      sessions: [
        { id: "1", date: "2026-05-20", topic: "分布式 · 高并发", target_role: "后端", score: 8.5, pass_fail: "pass", key_issues: [], report: { technical_depth: 4, quantified_results: 4, failure_tradeoffs: 4, structure: 4, key_concepts: ["缓存", "短链接"], highlights: [], improvements: [] } },
        { id: "2", date: "2026-05-19", topic: "分布式 · 消息队列", target_role: "后端", score: 8.0, pass_fail: "pass", key_issues: [], report: { technical_depth: 4, quantified_results: 4, failure_tradeoffs: 4, structure: 4, key_concepts: ["Kafka", "幂等性"], highlights: [], improvements: [] } },
      ]
    });
    mockFetchOpening.mockResolvedValue({
      greeting: "欢迎回来",
      weakness_summary: "量化不足",
      evidence: "5 场",
      focus_today: "重点练习",
      cta_type: "returning",
    });
  });

  it("加载期间显示骨架屏", () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // 永不 resolve
    render(<CoachDashboard />);
    expect(screen.getByTestId("coach-skeleton")).toBeInTheDocument();
  });

  it("老用户在 prepare 阶段显示欢迎语", async () => {
    mockFetch.mockResolvedValue({
      is_returning: true,
      target_role: "后端",
      target_company: null,
      user_background: null,
      session_count: 7,
      last_session_id: "sid-123",
      resume_filename: "resume.pdf",
    });

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/欢迎回来/)).toBeInTheDocument();
    });
  });

  it("已有简历解析出的岗位时不再显示首场面试设置卡", async () => {
    mockFetch.mockResolvedValue({
      is_returning: false,
      target_role: "WEB前端工程师",
      target_company: null,
      user_background: null,
      session_count: 0,
      last_session_id: null,
      resume_filename: "resume.pdf",
    });

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "直接开始面试" })).toBeInTheDocument();
    });
    expect(screen.queryByText("开启你的第一场面试")).not.toBeInTheDocument();
    expect(screen.queryByText("你想练习的岗位")).not.toBeInTheDocument();
  });

  it("当 stage 为 interview 时显示进行中提示", async () => {
    mockFetchUserStage.mockResolvedValue("interview");
    mockFetch.mockResolvedValue({
      is_returning: true,
      target_role: "后端",
      target_company: null,
      user_background: null,
      session_count: 5,
      last_session_id: "sid-456",
      resume_filename: "resume.pdf",
    });

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/后端 面试正在进行中/)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "立即返回面试间" })).toBeInTheDocument();
  });

  it("当 stage 为 coach 时显示开始复盘按钮，点击后触发 SSE", async () => {
    mockFetchUserStage.mockResolvedValue("coach");
    mockFetch.mockResolvedValue({
      is_returning: true,
      target_role: "后端",
      target_company: null,
      user_background: null,
      session_count: 5,
      last_session_id: "session-123",
      resume_filename: "resume.pdf",
    });
    
    // Mock 全局 fetch 用于 SSE
    const mockResponse = {
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn().mockResolvedValueOnce({ done: true })
        })
      }
    };
    global.fetch = vi.fn().mockResolvedValue(mockResponse as any);

    const { getByText } = render(<CoachDashboard />);

    // 1. 等待加载完成并显示按钮
    await waitFor(() => {
      expect(screen.getByText("面试已圆满结束")).toBeInTheDocument();
    });

    // 2. 点击开始复盘
    const startBtn = screen.getByRole("button", { name: /开始深度复盘/ });
    fireEvent.click(startBtn);

    // 3. 验证 SSE 触发
    await waitFor(() => {
      expect(screen.getByText(/正在深度复盘本次面试/)).toBeInTheDocument();
    });
    expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/v1/coach/review?session_id=session-123"), expect.anything());
  });

  describe("from=interview 软提示", () => {
    beforeEach(() => {
      mockReplace.mockClear();
      mockFetch.mockResolvedValue({
        is_returning: true,
        target_role: "后端",
        target_company: null,
        user_background: null,
        session_count: 7,
        last_session_id: null,
        resume_filename: "resume.pdf",
      });
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("URL 不带 from=interview 时不显示软提示", () => {
      mockSearchParams.mockReturnValue(new URLSearchParams(""));
      render(<CoachDashboard />);
      expect(screen.queryByText(/先在这里告诉我练什么/)).not.toBeInTheDocument();
    });
  });
});
