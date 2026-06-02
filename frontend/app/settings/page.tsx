import { AppShell } from "../components/app-shell";
import { SettingsView } from "./settings-view";

/** 渲染设置页面。 */
export default function SettingsPage() {
  return (
    <AppShell>
      <SettingsView />
    </AppShell>
  );
}
