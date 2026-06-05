import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MainNav } from "./nav";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    className,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

import { usePathname } from "next/navigation";
const mockUsePathname = vi.mocked(usePathname);

describe("MainNav", () => {
  beforeEach(() => {
    mockUsePathname.mockReturnValue("/");
  });

  it("渲染所有导航菜单项（不含已收紧的面试房间）", () => {
    render(<MainNav isLoggedIn={true} />);
    expect(screen.getByText("Coach")).toBeInTheDocument();
    // 面试房间已收紧为 Coach 的派生入口，不在导航栏单列
    expect(screen.queryByText("面试房间")).not.toBeInTheDocument();
    expect(screen.getByText("个人仪表盘")).toBeInTheDocument();
    expect(screen.getByText("test")).toBeInTheDocument();
    expect(screen.getByText("设置")).toBeInTheDocument();
  });

  it("根据当前路径高亮对应菜单项", () => {
    mockUsePathname.mockReturnValue("/dashboard");
    render(<MainNav isLoggedIn={true} />);
    expect(screen.getByText("个人仪表盘").className).toContain("active");
    expect(screen.getByText("Coach").className).not.toContain("active");
  });

  it("在 /interview 路径下应高亮 Coach 菜单项", () => {
    mockUsePathname.mockReturnValue("/interview");
    render(<MainNav isLoggedIn={true} />);
    expect(screen.getByText("Coach").className).toContain("active");
  });

  it("在 /interview/ 路径下应高亮 Coach 菜单项", () => {
    mockUsePathname.mockReturnValue("/interview/session123");
    render(<MainNav isLoggedIn={true} />);
    expect(screen.getByText("Coach").className).toContain("active");
  });

  it("在 /test 路径下应高亮 test 菜单项", () => {
    mockUsePathname.mockReturnValue("/test");
    render(<MainNav isLoggedIn={true} />);
    expect(screen.getByText("test").className).toContain("active");
    expect(screen.getByText("Coach").className).not.toContain("active");
  });

  it("未登录时显示登录链接", () => {
    render(<MainNav isLoggedIn={false} />);
    expect(screen.getByText("登录")).toBeInTheDocument();
  });

  it("已登录时不显示登录链接", () => {
    render(<MainNav isLoggedIn={true} />);
    expect(screen.queryByText("登录")).not.toBeInTheDocument();
  });

  it("在 /login 路径且未登录时，登录链接有 active 样式", () => {
    mockUsePathname.mockReturnValue("/login");
    render(<MainNav isLoggedIn={false} />);
    expect(screen.getByText("登录").className).toContain("active");
  });
});
