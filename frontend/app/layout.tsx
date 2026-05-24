import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
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

/** 渲染应用根布局，字体通过 next/font 在构建期打包，不依赖 Google CDN。 */
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
