import Image from "next/image";
import Link from "next/link";
import { UserButton } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import { MainNav } from "./nav";

/** 渲染全站页眉和主内容外壳。 */
export async function AppShell({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // /login 和 /sign-up 不经过 Clerk 中间件，auth() 会抛出，此时视为未登录
  let userId: string | null = null;
  try {
    ({ userId } = await auth());
  } catch {
    userId = null;
  }

  return (
    <div className="mac-app">
      <header className="mac-header">
        <Link className="mac-logo-area" href="/login" aria-label="Multi Agent Coach 首页">
          <div className="mac-logo-mark">
            <Image src="/vite.svg" alt="" width={24} height={24} priority />
          </div>
          <div className="mac-logo-text">
            Multi Agent <span>Coach</span>
          </div>
        </Link>
        <MainNav isLoggedIn={!!userId} />
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
