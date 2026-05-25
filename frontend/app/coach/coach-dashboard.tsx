"use client";

import React, { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@clerk/nextjs";
import { fetchInterviewContext, resetInterviewSession, type UserContextResponse } from "@/lib/interview-chat";

// 7 场历史面试 Mock 数据（本期仍用于展示卡片，但场次总数改用 contextData.session_count）
const MOCK_HISTORY = [
  { id: 37, score: 7.2, trend: "↗ +0.4", type: "improving", date: "5月15日 · 多 Agent" },
  { id: 36, score: 6.8, trend: "↘ -0.3", type: "declining", date: "5月12日 · 多 Agent" },
  { id: 35, score: 7.1, trend: "→ 0", type: "flat", date: "5月10日 · 单 Agent" },
  { id: 34, score: 7.1, trend: "↗ +0.5", type: "improving", date: "5月8日 · 多 Agent" },
  { id: 33, score: 6.6, trend: "↘ -0.4", type: "declining", date: "5月6日 · 多 Agent" },
  { id: 32, score: 7.0, trend: "→ 0", type: "flat", date: "5月4日 · 单 Agent" },
  { id: 31, score: 7.0, trend: "↗ +0.6", type: "improving", date: "5月2日 · 多 Agent" },
];

export function CoachDashboard() {
  const router = useRouter();
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [contextData, setContextData] = useState<UserContextResponse | null>(null);

  // userState 兼容现有状态机，is_returning 对应 "returning"，否则 "new"
  const userState: "returning" | "new" = contextData?.is_returning ? "returning" : "new";
  
  const [isThinking, setIsThinking] = useState(false);
  const [inputText, setInputText] = useState("");
  
  // 聊天上下文状态机
  const [userMessage, setUserMessage] = useState<string | null>(null);
  const [speechStage, setSpeechStage] = useState<
    "initial" | "follow" | "switch" | "switch-target" | "new-role" | "custom-reply"
  >("initial");
  
  const [selectedRole, setSelectedRole] = useState("");
  const [selectedTargetLabel, setSelectedTargetLabel] = useState("");

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // API 加载 effect
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    getToken().then(async (token) => {
      if (!token) { setIsLoading(false); return; }
      try {
        const data = await fetchInterviewContext({ token });
        setContextData(data);
      } catch {
        // 降级为新用户 UI
      } finally {
        setIsLoading(false);
      }
    });
  }, [isLoaded, isSignedIn, getToken]);

  // 重置交互阶段
  const resetConversation = () => {
    setUserMessage(null);
    setIsThinking(false);
    setInputText("");
    setSpeechStage("initial");
    setSelectedRole("");
    setSelectedTargetLabel("");
  };

  // 处理输入框高度自适应
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 96)}px`;
    }
  }, [inputText]);

  // 发送消息交互
  const handleSend = () => {
    const text = inputText.trim();
    if (!text) return;
    
    setUserMessage(text);
    setInputText("");
    setIsThinking(true);
    
    // 1.4s 呼吸思考动效后，Coach 回应
    setTimeout(() => {
      setIsThinking(false);
      setSpeechStage("custom-reply");
    }, 1400);
  };

  // 监听回车发送
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 处理 CTA 的点击事件
  const handleAction = async (action: string, extra?: string) => {
    if (action === "follow") {
      setIsThinking(true);
      setTimeout(() => {
        setIsThinking(false);
        setSpeechStage("follow");
      }, 1200);
    } else if (action === "switch") {
      setIsThinking(true);
      setTimeout(() => {
        setIsThinking(false);
        setSpeechStage("switch");
      }, 1200);
    } else if (action === "switch-target" && extra) {
      setSelectedTargetLabel(extra);
      setIsThinking(true);
      setTimeout(() => {
        setIsThinking(false);
        setSpeechStage("switch-target");
      }, 1000);
    } else if (action === "new-role" && extra) {
      setSelectedRole(extra);
      setUserMessage(`我在准备 ${extra} 的面试`);
      setIsThinking(true);
      setTimeout(() => {
        setIsThinking(false);
        setSpeechStage("new-role");
      }, 1100);
    } else if (action === "reset") {
      resetConversation();
    } else if (action === "go-room") {
      const role = selectedRole || contextData?.target_role || "";
      const bg = userMessage || contextData?.user_background || "";
      if (role) {
        sessionStorage.setItem(
          "interview_context",
          JSON.stringify({ target_role: role, user_background: bg }),
        );
        const token = await getToken();
        if (token) {
          await resetInterviewSession({
            token,
            target_role: role,
            user_background: bg || undefined,
          });
        }
      }
      router.push("/interview");
    } else if (action === "go-setup") {
      router.push("/settings");
    }
  };

  return (
    <div className="w-full max-w-[760px] mx-auto flex flex-col gap-7 relative py-3 md:py-6">
      
      {isLoading && (
        <div data-testid="coach-skeleton" className="animate-pulse space-y-4 py-6">
          <div className="h-6 w-48 rounded bg-[#e8e7e2]" />
          <div className="h-4 w-72 rounded bg-[#e8e7e2]" />
          <div className="h-4 w-56 rounded bg-[#e8e7e2]" />
        </div>
      )}

      {!isLoading && (
        <>
          {/* 1. Coach 身份条 */}
          <div className="flex items-center gap-3.5 pb-4.5 pr-[220px] max-[768px]:pr-0 border-b border-[#e8e7e2]">
            <div className="relative w-[52px] h-[52px] rounded-full shrink-0 bg-gradient-to-br from-[#7c3aed] to-[#4f46e5] text-white font-[var(--mac-font-display)] text-[22px] flex items-center justify-center shadow-[0_0_0_4px_rgba(124,58,237,0.08),0_6px_18px_rgba(124,58,237,0.18)] select-none">
              C
              <span
                className={`absolute right-[-1px] bottom-[-1px] w-3 h-3 rounded-full border-2 border-white transition-colors duration-300 ${
                  userState === "returning" ? "bg-[#059669]" : "bg-[#7c3aed]"
                }`}
              />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-[var(--mac-font-display)] text-xl text-[#171717] leading-tight">Coach</div>
              {userState === "returning" ? (
                <div className="text-xs text-[#8a8a8a] mt-1 flex gap-2 items-center">
                  <span>你的 AI 面试教练</span>
                  <span className="w-0.75 h-0.75 rounded-full bg-[#8a8a8a]" />
                  <span>已陪你 <b className="text-[#525252] font-semibold">{contextData?.session_count ?? 0} 场</b></span>
                </div>
              ) : (
                <div className="text-xs text-[#8a8a8a] mt-1 flex gap-2 items-center">
                  <span>你的 AI 面试教练</span>
                  <span className="w-0.75 h-0.75 rounded-full bg-[#8a8a8a]" />
                  <span>我们第一次见面</span>
                </div>
              )}
            </div>
          </div>

          {/* 2. 用户消息气泡（每轮覆盖显示最新一条） */}
          {userMessage && (
            <div className="flex justify-end px-1 animate-in fade-in slide-in-from-bottom-2 duration-300">
              <div>
                <div className="max-w-[78%] ml-auto px-3.5 py-2.5 bg-white border border-[#e8e7e2] rounded-[14px_14px_4px_14px] text-[#171717] text-[13px] leading-[1.55] shadow-xs">
                  {userMessage}
                </div>
                <div className="text-[10px] text-[#8a8a8a] mt-1 text-right pr-1">
                  刚刚 · 你
                </div>
              </div>
            </div>
          )}

          {/* 3. Coach 呼吸思考状态 */}
          {isThinking && (
            <div className="flex gap-4 px-1 animate-in fade-in duration-200">
              <div className="w-[2px] shrink-0 rounded-[2px] bg-[#7c3aed] opacity-30" />
              <div className="flex items-center gap-2.5 text-[#8a8a8a] text-[13px] font-sans">
                <div className="w-2 h-2 rounded-full bg-[#7c3aed] animate-coach-pulse" />
                <span>Coach 正在回...</span>
              </div>
            </div>
          )}

          {/* 4. Coach 说话文字区 */}
          {!isThinking && (
            <div className="flex gap-4 px-1 animate-in fade-in duration-300">
              <div className="w-[2px] shrink-0 rounded-[2px] bg-gradient-to-b from-[#7c3aed] to-[#4f46e5] opacity-50" />
              <div className="flex-1 font-[var(--mac-font-display)] text-xl md:text-[22px] leading-[1.55] text-[#171717] font-normal">
                
                {/* 4.1 初始阶段（开场两态） */}
                {speechStage === "initial" && (
                  <>
                    {userState === "returning" ? (
                      <div>
                        <p>欢迎回来。</p>
                        <p className="mt-3.5">
                          我看了你过去 {contextData?.session_count ?? 0} 场面试，发现一个挺要命的规律 ——<br />
                          你讲项目时，<span className="text-[#e11d48] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(225,29,72,0.16)_62%)] font-sans">结果指标永远是模糊的</span>，7 场里有 <span className="text-[#e11d48] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(225,29,72,0.16)_62%)] font-sans">5 场</span> 都被扣。
                        </p>
                        <p className="mt-3.5">今天我想让你重练，<span className="text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans">这次你必须给我数字</span>。</p>
                      </div>
                    ) : (
                      <div>
                        <p>你好。我还不认识你。</p>
                        <p className="mt-3.5">
                          我是你的 AI 面试教练 —— 我会陪你练面试，记住你讲过的每个项目，<br />
                          然后告诉你 <span className="text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans">下次该怎么讲会更好</span>。
                        </p>
                        <p className="mt-3.5">开始之前，先告诉我：你正在准备 <span className="text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans">什么岗位</span>？</p>
                      </div>
                    )}
                  </>
                )}

                {/* 4.2 点击“好，今天就练这个”后的“进入考场”卡片渲染 */}
                {speechStage === "follow" && (
                  <div>
                    <p>好。<span className="text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans">2 秒</span>给我，HR 准备好了。</p>
                    
                    <Card className="my-3.5 p-3.5 px-4 border border-[#7c3aed]/20 rounded-2xl bg-gradient-to-br from-[#f5f3ff] to-[#7c3aed]/[0.04] shadow-[0_4px_14px_rgba(124,58,237,0.08)] ring-0 font-sans gap-0">
                      <div className="text-[10px] font-extrabold tracking-[0.12em] uppercase text-[#7c3aed] mb-1.5 select-none">即将进入</div>
                      <div className="font-[var(--mac-font-display)] text-lg text-[#171717] leading-tight mb-1">第 #{(contextData?.session_count ?? 0) + 1} 场 · 多 Agent 委员会</div>
                      <div className="text-xs text-[#8a8a8a] flex gap-2.5 flex-wrap mt-1">
                        <span>本场重点 <b className="text-[#525252] font-semibold">量化结果 · 失败降级</b></span>
                        <span>预计 <b className="text-[#525252] font-semibold">30 min</b></span>
                      </div>
                    </Card>
                  </div>
                )}

                {/* 4.3 点击“等等，我想换方向” */}
                {speechStage === "switch" && (
                  <div>
                    <p>好。那你今天想换的是 ——</p>
                  </div>
                )}

                {/* 4.4 选了要换什么（岗位/技术栈/项目） */}
                {speechStage === "switch-target" && (
                  <div>
                    <p>明白。我把<span className="text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans">{selectedTargetLabel}</span>选择页打开给你。</p>
                  </div>
                )}

                {/* 4.5 新用户点选了岗位 */}
                {speechStage === "new-role" && (
                  <div>
                    <p>好。<span className="text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans">{selectedRole}</span>。</p>
                    <p className="mt-3.5">
                      那再给我一分钟 —— 用一两句话告诉我，<br />
                      你最想拿出来讲的<span className="text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans">那个项目</span>，是什么？
                    </p>
                  </div>
                )}

                {/* 4.6 底部发送消息后 */}
                {speechStage === "custom-reply" && (
                  <div>
                    <p>听到了。</p>
                    <p className="mt-3.5">我先把这条记下来，<span className="text-[#4f46e5] px-0.5 bg-[linear-gradient(180deg,transparent_62%,rgba(79,70,229,0.16)_62%)] font-sans">下一场会带着这个上下文</span>开始。</p>
                    <p className="mt-3.5">你现在想要 ——</p>
                  </div>
                )}

              </div>
            </div>
          )}

          {/* 5. 行动 CTA 区域（根据状态机做对应渲染） */}
          {!isThinking && (
            <div className="flex gap-2.5 flex-wrap pl-[18px] mt-1 animate-in fade-in duration-300">
              
              {/* 5.1 初始阶段（老用户） */}
              {userState === "returning" && speechStage === "initial" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAction("follow")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-transparent transition-all bg-[#171717] text-white shadow-[0_6px_18px_rgba(23,23,23,0.18)] hover:bg-black hover:translate-y-[-1px]"
                  >
                    好，今天就练这个
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("switch")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-[#dcdbd5] transition-all bg-white text-[#525252] hover:border-[#b8b5aa] hover:text-[#171717]"
                  >
                    等等，我想换方向
                  </button>
                </>
              )}

              {/* 5.2 初始阶段（新用户） */}
              {userState === "new" && speechStage === "initial" && (
                <>
                  {["AI Agent 工程师", "前端工程师", "后端工程师", "Python 工程师", "全栈工程师"].map((role) => (
                    <button
                      key={role}
                      type="button"
                      onClick={() => handleAction("new-role", role)}
                      className={`px-3.5 py-2 rounded-full border text-xs font-sans cursor-pointer transition-all hover:border-[#171717] hover:text-[#171717] hover:translate-y-[-1px] ${
                        role === "AI Agent 工程师"
                          ? "bg-[#171717] text-white border-[#171717] font-semibold hover:bg-black"
                          : "bg-white border-[#dcdbd5] text-[#525252]"
                      }`}
                    >
                      {role}
                    </button>
                  ))}
                </>
              )}

              {/* 5.3 进入考场确认页 (follow) */}
              {speechStage === "follow" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAction("go-room")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-transparent transition-all bg-[#171717] text-white shadow-[0_6px_18px_rgba(23,23,23,0.18)] hover:bg-black hover:translate-y-[-1px]"
                  >
                    进入考场
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("reset")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-[#dcdbd5] transition-all bg-white text-[#525252] hover:border-[#b8b5aa] hover:text-[#171717]"
                  >
                    算了，再聊聊
                  </button>
                </>
              )}

              {/* 5.4 换方向选项页 (switch) */}
              {speechStage === "switch" && (
                <>
                  {[
                    { key: "role", label: "换个目标岗位" },
                    { key: "stack", label: "换个技术栈" },
                    { key: "project", label: "换个项目讲" },
                  ].map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => handleAction("switch-target", item.label)}
                      className="px-3.5 py-2 rounded-full bg-white border border-[#dcdbd5] text-[#525252] text-xs font-sans cursor-pointer transition-all hover:border-[#171717] hover:text-[#171717] hover:translate-y-[-1px]"
                    >
                      {item.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => handleAction("reset")}
                    className="px-3.5 py-2 rounded-full bg-white border border-[#dcdbd5] text-[#525252] text-xs font-sans cursor-pointer transition-all hover:border-[#171717] hover:text-[#171717] hover:translate-y-[-1px]"
                  >
                    我想想，先回到刚才
                  </button>
                </>
              )}

              {/* 5.5 跳转至配置确认页 (switch-target) */}
              {speechStage === "switch-target" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAction("go-setup")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-transparent transition-all bg-[#171717] text-white shadow-[0_6px_18px_rgba(23,23,23,0.18)] hover:bg-black hover:translate-y-[-1px]"
                  >
                    打开
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("reset")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-[#dcdbd5] transition-all bg-white text-[#525252] hover:border-[#b8b5aa] hover:text-[#171717]"
                  >
                    不了
                  </button>
                </>
              )}

              {/* 5.6 新用户选择岗位后的确认 */}
              {speechStage === "new-role" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAction("go-setup")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-transparent transition-all bg-[#171717] text-white shadow-[0_6px_18px_rgba(23,23,23,0.18)] hover:bg-black hover:translate-y-[-1px]"
                  >
                    我直接试一场吧
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("reset")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-[#dcdbd5] transition-all bg-white text-[#525252] hover:border-[#b8b5aa] hover:text-[#171717]"
                  >
                    让我想想
                  </button>
                </>
              )}

              {/* 5.7 底部发送消息后 */}
              {speechStage === "custom-reply" && (
                <>
                  <button
                    type="button"
                    onClick={() => handleAction("go-room")}
                    className="px-5.5 py-3 rounded-2xl font-sans text-sm font-semibold cursor-pointer border border-transparent transition-all bg-[#171717] text-white shadow-[0_6px_18px_rgba(23,23,23,0.18)] hover:bg-black hover:translate-y-[-1px]"
                  >
                    直接进考场
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("go-setup")}
                    className="px-3.5 py-2 rounded-full bg-white border border-[#dcdbd5] text-[#525252] text-xs font-sans cursor-pointer transition-all hover:border-[#171717] hover:text-[#171717] hover:translate-y-[-1px]"
                  >
                    先调一下配置
                  </button>
                  <button
                    type="button"
                    onClick={() => handleAction("reset")}
                    className="px-3.5 py-2 rounded-full bg-white border border-[#dcdbd5] text-[#525252] text-xs font-sans cursor-pointer transition-all hover:border-[#171717] hover:text-[#171717] hover:translate-y-[-1px]"
                  >
                    再聊聊
                  </button>
                </>
              )}

            </div>
          )}

          {/* 6. 历史面试记忆（仅在老用户态下展示） */}
          {userState === "returning" && (
            <div className="mt-2.5 pt-5.5 border-t border-[#e8e7e2] animate-in fade-in duration-300">
              <div className="text-[10px] font-extrabold tracking-[0.12em] uppercase text-[#8a8a8a] mb-3 select-none">
                你的 {contextData?.session_count ?? 0} 场记忆
              </div>
              
              <div className="flex gap-2 overflow-x-auto pb-1 custom-textarea-scrollbar">
                {MOCK_HISTORY.map((item) => (
                  <Card
                    key={item.id}
                    onClick={() => handleAction("go-setup")}
                    className="shrink-0 px-3.5 py-2.5 rounded-[10px] border border-[#e8e7e2] bg-white flex flex-col gap-0.5 min-w-[102px] cursor-pointer transition-all hover:border-[#dcdbd5] hover:translate-y-[-1px] ring-0 gap-0"
                  >
                    <div className="text-[11px] text-[#8a8a8a] font-semibold select-none">#{item.id}</div>
                    <div className={`font-[var(--mac-font-display)] text-lg flex items-baseline gap-1 ${
                      item.type === "improving"
                        ? "text-[#059669]"
                        : item.type === "declining"
                        ? "text-[#e11d48]"
                        : "text-[#171717]"
                    }`}>
                      {item.score.toFixed(1)}
                      <span className={`text-[10px] font-sans font-semibold ${
                        item.type === "improving"
                          ? "text-[#059669]"
                          : item.type === "declining"
                          ? "text-[#e11d48]"
                          : "text-[#8a8a8a]"
                      }`}>
                        {item.trend}
                      </span>
                    </div>
                    <div className="text-[10px] text-[#8a8a8a] mt-0.5">{item.date}</div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* 7. 底部回应输入框区域 */}
          <div className="mt-1.5">
            <div className="p-3 bg-white border border-[#e8e7e2] rounded-[14px] shadow-sm flex items-end gap-2.5">
              <textarea
                ref={textareaRef}
                rows={1}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="或者直接告诉我你想聊什么..."
                className="flex-1 border-0 outline-none resize-none bg-transparent text-[#171717] text-sm leading-relaxed p-1.5 py-1 min-h-[28px] max-h-[96px] focus-visible:ring-0 focus-visible:ring-offset-0 focus:outline-none focus:ring-0 custom-textarea-scrollbar font-sans"
              />
              <button
                type="button"
                onClick={handleSend}
                className="w-[38px] h-[38px] rounded-[10px] bg-[#171717] text-white flex items-center justify-center transition-all cursor-pointer hover:bg-black hover:translate-y-[-1px] select-none text-[18px]"
              >
                ↑
              </button>
            </div>
            <div className="pl-1 text-[11px] text-[#8a8a8a] mt-1.5 select-none">
              按 Enter 发送 · Shift + Enter 换行
            </div>
          </div>
        </>
      )}

    </div>
  );
}
