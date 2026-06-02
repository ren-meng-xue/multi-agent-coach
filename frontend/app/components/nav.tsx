"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { label: "Coach", href: "/coach" },
  { label: "个人仪表盘", href: "/dashboard" },
  { label: "设置", href: "/settings" },
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
      {navItems.map((item) => {
        const isActive =
          item.href === "/coach"
            ? pathname === "/coach" ||
              pathname.startsWith("/coach/") ||
              pathname === "/interview" ||
              pathname.startsWith("/interview/")
            : pathname === item.href || pathname.startsWith(item.href + "/");
        return (
          <Link
            className={`mac-nav-item ${isActive ? "active" : ""}`}
            href={item.href}
            key={item.href}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
