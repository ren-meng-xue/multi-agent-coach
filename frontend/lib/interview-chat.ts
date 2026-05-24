import { readSseStream, type SseEvent } from "./sse";

export type InterviewChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type StreamInterviewChatOptions = {
  token: string;
  messages: InterviewChatMessage[];
  signal?: AbortSignal;
  onDelta: (text: string) => void;
};

const DEFAULT_ERROR_MESSAGE = "请求失败，请稍后重试";

/** 调用后端面试聊天 SSE 接口，并把 delta 事件逐段交给 UI 层渲染。 */
export async function streamInterviewChat({
  token,
  messages,
  signal,
  onDelta,
}: StreamInterviewChatOptions): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) {
    throw new Error("缺少后端接口配置");
  }

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/interview/chat`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ messages }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(DEFAULT_ERROR_MESSAGE);
  }

  await readSseStream({
    stream: response.body,
    onEvent: (event) => handleSseEvent(event, onDelta),
  });
}

function handleSseEvent({ event, data }: SseEvent, onDelta: (text: string) => void) {
  if (event === "done") return;

  if (event === "delta") {
    const payload = parseJsonPayload<{ text?: string }>(data);
    if (payload.text) onDelta(payload.text);
    return;
  }

  if (event === "error") {
    const payload = parseJsonPayload<{ message?: string }>(data);
    throw new Error(payload.message || DEFAULT_ERROR_MESSAGE);
  }
}

function parseJsonPayload<T>(data: string): T {
  try {
    return JSON.parse(data) as T;
  } catch {
    throw new Error(DEFAULT_ERROR_MESSAGE);
  }
}
