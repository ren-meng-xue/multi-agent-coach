"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

const navItems = [
  { label: "Coach", href: "/coach" },
  { label: "个人仪表盘", href: "/dashboard" },
  { label: "设置", href: "/settings" },
];

/** 主导航栏，自动根据当前路径高亮对应菜单项。未登录点击保护页面时弹出登录提示。 */
export function MainNav({ isLoggedIn }: { isLoggedIn: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const [showLoginTip, setShowLoginTip] = useState(false);

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (!isLoggedIn) {
      e.preventDefault();
      setShowLoginTip(true);
    }
  };

  return (
    <>
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
              onClick={handleNavClick}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      {showLoginTip && (
        <div
          className="mac-modal-overlay"
          onClick={() => setShowLoginTip(false)}
        >
          <div className="mac-modal-card" onClick={(e) => e.stopPropagation()}>
            <p className="mac-modal-text">请先登录后使用此功能</p>
            <div className="mac-modal-actions">
              <button
                className="mac-modal-btn secondary"
                onClick={() => setShowLoginTip(false)}
              >
                稍后再说
              </button>
              <button
                className="mac-modal-btn primary"
                onClick={() => {
                  setShowLoginTip(false);
                  router.push("/login");
                }}
              >
                去登录
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
