"use client";

import type { MouseEvent, ReactNode } from "react";

/** 接管 Clerk footer 链接，确保登录/注册页之间稳定跳转。 */
export function AuthCardRouter({ children }: Readonly<{ children: ReactNode }>) {
  const handleClickCapture = (event: MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement | null;
    const link = target?.closest("a");
    const href = link?.getAttribute("href");
    const path = href ? new URL(href, window.location.origin).pathname : "";

    if (path === "/sign-up" || path === "/login") {
      event.preventDefault();
      event.stopPropagation();
      window.location.assign(path);
    }
  };

  return (
    <div data-auth-card-router="true" onClickCapture={handleClickCapture}>
      {children}
    </div>
  );
}
