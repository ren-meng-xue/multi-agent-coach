"use client";

import Image from "next/image";
import Link from "next/link";
import { UserButton, useAuth } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import { MainNav } from "./nav";

/** 渲染全站页眉和主内容外壳。 */
export function AppShell({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const { isLoaded, userId } = useAuth();
  const pathname = usePathname();

  // 解决登录 tab 闪烁问题：
  // 在 Clerk 加载完成前 (!isLoaded)，如果当前路径是 /login，则视为未登录状态以渲染登录 Tab；
  // 如果当前是其他被保护页面，则由于中间件已过滤未登录用户，先假设为已登录状态，避免已登录用户的布局闪烁。
  const isLoggedIn = isLoaded ? !!userId : pathname !== "/login";

  return (
    <div className="mac-app">
      <header className="mac-header">
        <Link className="mac-logo-area" href={isLoggedIn ? "/coach" : "/login"} aria-label="Multi Agent Coach 首页">
          <div className="mac-logo-mark">
            <Image src="/vite.svg" alt="" width={24} height={24} priority />
          </div>
          <div className="mac-logo-text">
            Multi Agent <span>Coach</span>
          </div>
        </Link>
        <MainNav isLoggedIn={isLoggedIn} />
        <div className="mac-header-actions">
          <UserButton />
        </div>
      </header>

      <main className="mac-main">{children}</main>
    </div>
  );
}

/** 渲染暂未实现功能页的占位内容。 */
export function PlaceholderPage({
  title,
  eyebrow,
}: Readonly<{
  title: string;
  eyebrow: string;
}>) {
  return (
    <AppShell>
      <section className="placeholder-panel">
        <div className="placeholder-icon" aria-hidden="true">
          <Image src="/vite.svg" alt="" width={34} height={34} priority />
        </div>
        <p>{eyebrow}</p>
        <h1>{title}</h1>
        <span>页面具体功能后续补充。</span>
      </section>
    </AppShell>
  );
}
