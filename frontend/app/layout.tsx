import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { zhCN } from "@clerk/localizations";
import { DM_Sans, DM_Serif_Display } from "next/font/google";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-dm-sans",
  display: "swap",
});

const dmSerifDisplay = DM_Serif_Display({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-dm-serif-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Multi Agent Coach — AI 面试陪练数字分身",
  description: "Multi Agent Coach 登录入口",
};

/** 扩展中文包，补全漏掉的错误提示。 */
const customLocalization: any = {
  ...zhCN,
  unstable__errors: {
    ...(zhCN as any).unstable__errors,
    form_identifier_exists: "该电子邮件地址已被占用。请尝试另一个。",
    form_password_pwned: "这个密码在数据泄露中被发现，不能使用，请换一个密码试试。",
  }
};

/** 从 Clerk publishable key 解析出 Frontend API 域，用于 preconnect。 */
function deriveClerkFapiOrigin(): string | null {
  const key = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";
  const match = key.match(/^pk_(?:test|live)_(.+)$/);
  if (!match) return null;
  try {
    const decoded = Buffer.from(match[1], "base64").toString().replace(/\$$/, "");
    return decoded ? `https://${decoded}` : null;
  } catch {
    return null;
  }
}

/** 渲染应用根布局。 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const clerkFapiOrigin = deriveClerkFapiOrigin();

  return (
    <ClerkProvider
      signInUrl="/login"
      signUpUrl="/sign-up"
      afterSignOutUrl="/login"
      localization={customLocalization as any}
      telemetry={false}
    >
      <html
        lang="zh-CN"
        className={`h-full antialiased ${dmSans.variable} ${dmSerifDisplay.variable}`}
        suppressHydrationWarning
      >
        <head>
          {clerkFapiOrigin && (
            <link rel="preconnect" href={clerkFapiOrigin} crossOrigin="anonymous" />
          )}
          {clerkFapiOrigin && (
            <link rel="dns-prefetch" href={clerkFapiOrigin} />
          )}
        </head>
        <body className="min-h-full flex flex-col">{children}</body>
      </html>
    </ClerkProvider>
  );
}
