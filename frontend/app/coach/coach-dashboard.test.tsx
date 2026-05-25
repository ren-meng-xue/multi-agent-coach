import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { CoachDashboard } from "./coach-dashboard";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: true,
    getToken: vi.fn().mockResolvedValue("test-token"),
  }),
}));

vi.mock("@/lib/interview-chat", () => ({
  fetchInterviewContext: vi.fn(),
  resetInterviewSession: vi.fn().mockResolvedValue(undefined),
}));

import { fetchInterviewContext } from "@/lib/interview-chat";
const mockFetch = vi.mocked(fetchInterviewContext);

describe("CoachDashboard", () => {
  beforeEach(() => {
    mockFetch.mockReset();
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
      target_company: null,
      user_background: "LangGraph 系统",
      session_count: 7,
    });

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/欢迎回来/)).toBeInTheDocument();
    });
    expect(screen.getAllByText(/7 场/)[0]).toBeInTheDocument();
    expect(screen.queryByTestId("coach-skeleton")).not.toBeInTheDocument();
  });

  it("新用户：显示「你好，我还不认识你」和岗位选择按钮", async () => {
    mockFetch.mockResolvedValue({
      is_returning: false,
      target_role: null,
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

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/还不认识你/)).toBeInTheDocument();
    });
  });
});
