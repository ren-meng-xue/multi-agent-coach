import { ClerkLoaded, ClerkLoading, SignIn, SignUp } from "@clerk/nextjs";
import { AuthCardRouter } from "./auth-card-router";
import { AppShell } from "./app-shell";

const features = [
  {
    title: "8 角色多 Agent 协作",
    text: "HR、技术、BOSS、Coach 等全流程仿真，覆盖行为面到终面。",
  },
  {
    title: "跨会话分级长期记忆",
    text: "跨会话记住 STAR 故事、能力曲线、答题盲点，越练越懂你。",
  },
  {
    title: "Reflexion 自反思引擎",
    text: "Agent 答题后自我反思打分，并针对性反向出题攻克弱项。",
  },
];

const clerkAppearance = {
  elements: {
    rootBox: "mac-clerk-root",
    cardBox: "mac-clerk-card-box",
    card: "mac-clerk-card",
    header: "mac-clerk-header",
    headerTitle: "mac-clerk-title",
    headerSubtitle: "mac-clerk-subtitle",
    socialButtonsBlockButton: "mac-clerk-social-btn",
    dividerLine: "mac-clerk-divider-line",
    dividerText: "mac-clerk-divider-text",
    formFieldLabel: "mac-clerk-label",
    formFieldInput: "mac-clerk-input",
    formButtonPrimary: "mac-clerk-primary",
    footerActionText: "mac-clerk-footer-text",
    footerActionLink: "mac-clerk-footer-link",
  },
};

type AuthMode = "sign-in" | "sign-up";

/** 渲染 Clerk 初始化期间的等高骨架屏，避免右侧卡片空白。 */
function AuthCardSkeleton() {
  return (
    <div className="mac-clerk-skeleton" aria-label="认证表单加载中">
      <div className="mac-skeleton-title" />
      <div className="mac-skeleton-subtitle" />
      <div className="mac-skeleton-social-row">
        <div />
        <div />
      </div>
      <div className="mac-skeleton-divider" />
      <div className="mac-skeleton-field" />
      <div className="mac-skeleton-field" />
      <div className="mac-skeleton-button" />
      <div className="mac-skeleton-footer" />
    </div>
  );
}

/** 渲染登录/注册共享页面，保留原型分屏视觉并接入真实 Clerk 表单。 */
export function AuthPage({ mode }: Readonly<{ mode: AuthMode }>) {
  const isSignIn = mode === "sign-in";

  return (
    <AppShell>
      <section className="auth-split" aria-label="登录 Multi Agent Coach">
        <div className="auth-hero">
          <div className="auth-overline">AI 驱动的面试教练</div>
          <h1>
            你的 <b>AI 面试陪练</b>
            <br />
            数字分身
          </h1>
          <p className="auth-tagline">
            不只是模拟面试，而是一个会成长、会反思、会记住你的每一次进步的职业伙伴。
          </p>
          <div className="auth-features">
            {features.map((feature) => (
              <div className="auth-feat" key={feature.title}>
                <div className="feat-icon" aria-hidden="true">
                  ◆
                </div>
                <div>
                  <strong>{feature.title}</strong>
                  <span>{feature.text}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="auth-panel">
          <div className="clerk-card mac-real-clerk-card" aria-label="to continue to Multi Agent Coach">
            <ClerkLoading>
              <AuthCardSkeleton />
            </ClerkLoading>
            <ClerkLoaded>
              <AuthCardRouter>
                {isSignIn ? (
                  <SignIn
                    appearance={clerkAppearance}
                    path="/login"
                    routing="path"
                    signUpUrl="/sign-up"
                    fallbackRedirectUrl="/coach"
                  />
                ) : (
                  <SignUp
                    appearance={clerkAppearance}
                    path="/sign-up"
                    routing="path"
                    signInUrl="/login"
                    fallbackRedirectUrl="/coach"
                  />
                )}
              </AuthCardRouter>
            </ClerkLoaded>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
