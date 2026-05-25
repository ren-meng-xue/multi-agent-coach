import { AppShell } from "../components/app-shell";
import { CoachDashboard } from "./coach-dashboard";

/** 渲染 Coach 交互页面。 */
export default function CoachPage() {
  return (
    <AppShell>
      <CoachDashboard />
    </AppShell>
  );
}

