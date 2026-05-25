import { AppShell } from "../components/app-shell";
import { SettingsView } from "./settings-view";

/** 渲染设置与故事库页面。 */
export default function SettingsPage() {
  return (
    <AppShell>
      <SettingsView />
    </AppShell>
  );
}
