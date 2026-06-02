"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { AppShell } from "../components/app-shell";
import { DashboardContent } from "./dashboard-content";
import { fetchDashboardData, type DashboardData } from "@/lib/user";

const DEV_AUTH_BYPASS_TOKEN = "dev-auth-bypass-token";
const isDevAuthBypassEnabled = process.env.NEXT_PUBLIC_DEV_AUTH_BYPASS === "1";

/** 渲染个人仪表盘路由页面。 */
export default function DashboardPage() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!isLoaded || (!isSignedIn && !isDevAuthBypassEnabled)) {
      if (isLoaded) setIsLoading(false);
      return;
    }

    const fetchToken = isDevAuthBypassEnabled ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN) : getToken();

    void fetchToken.then(async (token) => {
      if (!token) {
        setIsLoading(false);
        return;
      }
      try {
        const dashboardData = await fetchDashboardData({ token });
        setData(dashboardData);
      } catch (error) {
        console.error("DashboardPage fetch error:", error);
      } finally {
        setIsLoading(false);
      }
    });
  }, [isLoaded, isSignedIn, getToken]);

  return (
    <AppShell>
      {isLoading ? (
        <div className="w-full max-w-[1200px] mx-auto animate-pulse space-y-8 mt-4">
           <div className="grid grid-cols-4 gap-4">
              {[1, 2, 3, 4].map(i => <div key={i} className="h-32 bg-[#e8e7e2] rounded-xl" />)}
           </div>
           <div className="grid grid-cols-2 gap-4">
              <div className="h-64 bg-[#e8e7e2] rounded-xl" />
              <div className="h-64 bg-[#e8e7e2] rounded-xl" />
           </div>
        </div>
      ) : data ? (
        <DashboardContent data={data} />
      ) : (
        <div className="flex items-center justify-center h-[60vh] text-gray-500">
           数据加载失败，请重试
        </div>
      )}
    </AppShell>
  );
}
