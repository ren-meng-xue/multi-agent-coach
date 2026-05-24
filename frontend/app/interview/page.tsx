import { AppShell } from "../components/app-shell";
import { InterviewChat } from "./_components/interview-chat";

/** 渲染面试房间的一问一答流式聊天页。 */
export default function InterviewPage() {
  return (
    <AppShell>
      <InterviewChat />
    </AppShell>
  );
}
