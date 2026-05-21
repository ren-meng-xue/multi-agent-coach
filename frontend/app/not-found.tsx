'use client'

import Image from "next/image";
import Link from "next/link";
import { ArrowLeft, Home, Search, HelpCircle } from "lucide-react";

/** 
 * 重新设计的 404 页面 - 系统一致风格
 * 使用 Tailwind 直接渲染以确保样式可靠性
 */
export default function NotFound() {
  return (
    <main className="relative min-h-screen w-full flex flex-col items-center justify-center bg-[#fafaf7] overflow-hidden px-5 py-10 font-sans selection:bg-indigo-100">
      {/* 背景纹理 */}
      <div 
        className="absolute inset-0 z-0 opacity-40 pointer-events-none" 
        style={{ 
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3E%3Cdefs%3E%3Cpattern id='g' width='60' height='60' patternUnits='userSpaceOnUse'%3E%3Cpath d='M30 5v50M5 30h50' stroke='%23e8e7e2' stroke-width='0.5' fill='none'/%3E%3C/pattern%3E%3C/defs%3E%3Crect width='60' height='60' fill='url(%23g)'/%3E%3C/svg%3E")` 
        }} 
      />
      
      <div className="relative z-10 w-full max-w-[900px] animate-in fade-in slide-in-from-bottom-5 duration-700">
        <div className="bg-white/70 backdrop-blur-xl border border-white rounded-[28px] shadow-[0_12px_40px_rgba(0,0,0,0.08)] p-8 md:p-12 relative overflow-hidden">
          {/* Mac 控制点 */}
          <div className="absolute top-6 left-6 flex gap-2">
            <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
            <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
            <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_1.2fr] gap-10 md:gap-16 items-center">
            {/* 视觉部分 */}
            <div className="flex justify-center order-first md:order-none">
              <div className="relative flex items-center justify-center">
                <div className="relative z-10 animate-bounce-subtle">
                  <Image
                    src="/404-astronaut.svg"
                    alt="404"
                    width={280}
                    height={280}
                    className="drop-shadow-2xl"
                    priority
                  />
                </div>
                {/* 雷达波纹 */}
                <div className="absolute w-24 h-24 border-2 border-indigo-500 rounded-full animate-mac-ping opacity-0" />
                <div className="absolute w-24 h-24 border-2 border-indigo-500 rounded-full animate-mac-ping-delay-1 opacity-0" />
              </div>
            </div>

            {/* 文字部分 */}
            <div className="flex flex-col gap-4 text-center md:text-left items-center md:items-start">
              <div className="flex items-center gap-2 text-indigo-600 text-[10px] font-extrabold tracking-widest uppercase mb-1">
                <HelpCircle size={14} />
                <span>STATUS: 404 NOT FOUND</span>
              </div>
              
              <h1 className="font-serif text-4xl md:text-5xl text-[#171717] leading-tight">
                页面迷航中...
              </h1>
              
              <p className="text-sm md:text-base text-[#525252] leading-relaxed max-w-[400px]">
                抱歉，我们无法在当前坐标找到该页面。它可能已经被移动、更名，或者正在深空信号盲区中。
              </p>

              <div className="flex flex-wrap gap-3 mt-4 justify-center md:justify-start">
                <Link 
                  href="/login" 
                  className="flex items-center gap-2 px-6 py-3 bg-[#4f46e5] hover:bg-[#4338ca] text-white rounded-xl font-semibold text-sm transition-all shadow-lg shadow-indigo-200 hover:-translate-y-0.5"
                >
                  <ArrowLeft size={18} />
                  <span>返回登录基地</span>
                </Link>
                <Link 
                  href="/dashboard" 
                  className="flex items-center gap-2 px-6 py-3 bg-white hover:bg-[#f5f4f0] text-[#171717] border border-[#dcdbd5] rounded-xl font-semibold text-sm transition-all hover:border-[#b8b5aa]"
                >
                  <Home size={18} />
                  <span>个人仪表盘</span>
                </Link>
              </div>
              
              <div className="mt-6 pt-6 border-t border-[#e8e7e2] w-full flex items-center gap-2 text-[#8a8a8a] text-xs justify-center md:justify-start">
                <Search size={14} />
                <span>尝试检查 URL 是否正确或联系系统管理员</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <footer className="mt-10 text-[#8a8a8a] text-xs text-center opacity-80">
        <p>© 2026 Multi Agent Coach. All Systems Operational.</p>
      </footer>

      <style jsx global>{`
        @keyframes bounce-subtle {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-15px); }
        }
        .animate-bounce-subtle {
          animation: bounce-subtle 4s ease-in-out infinite;
        }
        @keyframes mac-ping {
          0% { transform: scale(1); opacity: 0.6; }
          100% { transform: scale(3.5); opacity: 0; }
        }
        .animate-mac-ping {
          animation: mac-ping 3s ease-out infinite;
        }
        .animate-mac-ping-delay-1 {
          animation: mac-ping 3s ease-out infinite 1.5s;
        }
      `}</style>
    </main>
  );
}
