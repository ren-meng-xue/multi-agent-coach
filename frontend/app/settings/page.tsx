import { Suspense } from "react";

import { AppShell } from "../components/app-shell";
import { SettingsView } from "./settings-view";

/** 渲染设置页面。 */
export default function SettingsPage() {
  return (
    <AppShell>
      <Suspense
        fallback={
          <div className="flex min-h-[400px] items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#4f46e5]" />
          </div>
        }
      >
        <SettingsView />
      </Suspense>
    </AppShell>
  );
}
