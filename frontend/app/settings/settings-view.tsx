"use client";

import React, { useState, useEffect } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import { useSearchParams } from "next/navigation";
import {
  fetchUserProfile,
  type UserProfile,
} from "@/lib/user";
import { ResumeCard } from "./_components/resume-card";
import { Mail, Compass, Activity, Info, AlertCircle } from "lucide-react";

export function SettingsView() {
  const searchParams = useSearchParams();
  const showResumeAlert = searchParams.get("require_resume") === "1";
  
  const { isLoaded: authLoaded, isSignedIn, getToken } = useAuth();
  const { user: clerkUser } = useUser();
  const [loading, setLoading] = useState(true);
  const [authToken, setAuthToken] = useState("");
  const [profile, setProfile] = useState<UserProfile | null>(null);

  useEffect(() => {
    if (!authLoaded || !isSignedIn) return;

    const loadData = async () => {
      try {
        const token = await getToken();
        if (!token) return;
        setAuthToken(token);

        const userProfile = await fetchUserProfile({ token });
        setProfile(userProfile);
      } catch (error) {
        console.error("Failed to load settings:", error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [authLoaded, isSignedIn, getToken]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#4f46e5]"></div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-[1200px] mx-auto pt-0 pb-4 px-6 h-[calc(100vh-110px)] max-h-[calc(100vh-110px)] flex flex-col min-h-0 animate-in fade-in duration-500 font-sans text-[var(--mac-text-secondary)]">
      {/* 顶部大标题 */}
      <div className="mb-3.5 pb-2 border-b border-[var(--mac-border-light)] shrink-0">
        <h1 className="text-2xl font-normal text-[var(--mac-text-primary)] font-serif tracking-tight">
          个人设置
        </h1>
        <p className="text-xs text-[var(--mac-text-tertiary)] mt-1">
          管理您的个人资料、目标方向及个人简历，定制专属模拟实战演练方案。
        </p>
      </div>

      {showResumeAlert && (
        <div className="mb-4 p-3 bg-[#fef2f2] border border-[#fca5a5] rounded-[var(--mac-radius-sm)] text-xs flex items-center gap-2.5 text-[#991b1b] shrink-0">
          <AlertCircle className="size-4 text-[#ef4444] shrink-0" />
          <p className="font-medium">提示：为了能更好地进行面试准备，请在右侧完善您的个人简历。</p>
        </div>
      )}

      {/* 左右分栏 */}
      <div className="flex-1 min-h-0 flex flex-col md:flex-row gap-6 items-stretch">
        {/* 左侧：基本档案与提示 */}
        <div className="w-full md:w-1/3 flex flex-col min-h-0 overflow-y-auto pr-1 gap-4 shrink-0">
          <div className="border border-[var(--mac-border-light)] bg-white rounded-[var(--mac-radius)] shadow-[var(--mac-shadow-xs)] p-6 space-y-6 shrink-0">
            <div className="flex items-center gap-4 pb-4 border-b border-[var(--mac-border-light)]">
              <div className="w-10 h-10 border border-[var(--mac-border-light)] bg-[#fafaf8] flex items-center justify-center overflow-hidden rounded-[var(--mac-radius-xs)] shrink-0 shadow-xs">
                {clerkUser?.imageUrl ? (
                  <img src={clerkUser.imageUrl} alt="头像" className="w-full h-full object-cover" />
                ) : (
                  <span className="text-[var(--mac-text-primary)] text-base font-serif font-semibold">{clerkUser?.firstName?.charAt(0) || "用"}</span>
                )}
              </div>
              <div className="min-w-0">
                <span className="text-xs text-[var(--mac-text-tertiary)] block">求职人</span>
                <span className="text-base font-serif text-[var(--mac-text-primary)] truncate block">
                  {clerkUser?.fullName || "求职者"}
                </span>
              </div>
            </div>

            <div className="space-y-4 text-xs">
              <div className="flex gap-3 items-start">
                <Mail className="size-4 text-[var(--mac-text-tertiary)] mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <span className="text-[10px] text-[var(--mac-text-tertiary)] uppercase tracking-wider block mb-0.5">电子邮箱</span>
                  <span className="text-sm text-[var(--mac-text-primary)] font-mono truncate block">
                    {clerkUser?.primaryEmailAddress?.emailAddress || "未绑定"}
                  </span>
                </div>
              </div>

              <div className="flex gap-3 items-start">
                <Compass className="size-4 text-[var(--mac-text-tertiary)] mt-0.5 shrink-0" />
                <div>
                  <span className="text-[10px] text-[var(--mac-text-tertiary)] uppercase tracking-wider block mb-0.5">目标方向</span>
                  <span className="text-sm text-[var(--mac-text-primary)] font-serif">
                    {profile?.target_role || "未设定"}
                  </span>
                </div>
              </div>

              <div className="flex gap-3 items-start p-3 bg-[#fafaf8] border border-[var(--mac-border-light)] rounded-[var(--mac-radius-sm)]">
                <Activity className="size-4 text-[var(--mac-text-tertiary)] mt-0.5 shrink-0" />
                <div>
                  <span className="text-[10px] text-[var(--mac-text-tertiary)] uppercase tracking-wider block mb-0.5">演练进度</span>
                  <span className="text-xs text-[var(--mac-text-primary)] font-medium">
                    已经历 {profile?.total_sessions || 0} 次模拟实战
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* 演练准备提示 */}
          <div className="border border-[var(--mac-border-light)] bg-white rounded-[var(--mac-radius)] shadow-[var(--mac-shadow-xs)] p-6 space-y-3 shrink-0">
            <h3 className="text-xs font-semibold text-[var(--mac-text-primary)] uppercase tracking-wider flex items-center gap-2">
              <Info className="size-3.5 text-[var(--mac-text-tertiary)]" />
              <span>演练准备提示</span>
            </h3>
            <div className="text-xs text-[var(--mac-text-secondary)] leading-relaxed space-y-2 font-sans">
              <p>
                系统将根据您上传的个人简历，定制个性化的模拟实战演练。这能帮助您更好地在特定岗位和业务场景中展现自己的专业特长。
              </p>
              <p className="text-[var(--mac-text-tertiary)] text-[11px]">
                请确保您上传的简历包含您最真实的项目经历。完善的简历信息能够让 AI Coach 提供更具针对性的演练与深度反馈。
              </p>
            </div>
          </div>
        </div>

        {/* 右侧：个人简历 */}
        <div className="flex-1 w-full h-full min-h-0 flex flex-col">
          {profile && (
            <ResumeCard
              token={authToken}
              profile={profile}
              onUpdate={(updated) => setProfile(updated)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
