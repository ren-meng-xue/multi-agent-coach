import { Suspense } from "react";
import { AppShell } from "../components/app-shell";
import { CoachDashboard } from "./coach-dashboard";

/** 渲染 Coach 交互页面。 */
export default function CoachPage() {
  return (
    <AppShell>
      <Suspense fallback={
        <div className="animate-pulse space-y-4 py-6">
          <div className="h-6 w-48 rounded bg-[#e8e7e2]" />
          <div className="h-20 w-full rounded bg-[#e8e7e2]" />
          <div className="h-20 w-full rounded bg-[#e8e7e2]" />
        </div>
      }>
        <CoachDashboard />
      </Suspense>
    </AppShell>
  );
}

