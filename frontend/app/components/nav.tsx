"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { label: "Coach", href: "/coach" },
  { label: "面试房间", href: "/interview" },
  { label: "个人仪表盘", href: "/dashboard" },
  { label: "复盘报告", href: "/reports" },
  { label: "设置 & 故事库", href: "/settings" },
];

/** 主导航栏，自动根据当前路径高亮对应菜单项。 */
export function MainNav({ isLoggedIn }: { isLoggedIn: boolean }) {
  const pathname = usePathname();

  return (
    <nav className="mac-nav-wrap" aria-label="主导航">
      {!isLoggedIn && (
        <Link
          className={`mac-nav-item ${pathname === "/login" ? "active" : ""}`}
          href="/login"
        >
          登录
        </Link>
      )}
      {navItems.map((item) => (
        <Link
          className={`mac-nav-item ${pathname === item.href ? "active" : ""}`}
          href={item.href}
          key={item.href}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
