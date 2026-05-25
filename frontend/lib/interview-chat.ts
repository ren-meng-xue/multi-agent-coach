import { readSseStream, type SseEvent } from "./sse";

export type InterviewChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type InterviewProgressState = {
  stage: "opening" | "interview" | "closing";
  question_count: number;
  total_questions: number;
};

export interface InterviewReport {
  overall_score: number;
  technical_depth: number;
  quantified_results: number;
  failure_tradeoffs: number;
  structure: number;
  highlights: string[];
  improvements: string[];
}

export type UserContextResponse = {
  is_returning: boolean;
  target_role: string | null;
  work_years: string | null;
  target_company: string | null;
  user_background: string | null;
  session_count: number;
};

export type InterviewHistoryItem = {
  id: string;
  date: string;
  topic: string;
  target_role: string;
  score: number;
  pass_fail: "pass" | "fail" | "partial";
  key_issues: string[];
  report: any | null;
};

export type InterviewHistoryResponse = {
  sessions: InterviewHistoryItem[];
};

/** 返回用户的面试历史记录。 */
export async function fetchInterviewHistory({
  token,
  limit = 10,
}: {
  token: string;
  limit?: number;
}): Promise<InterviewHistoryResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) throw new Error("缺少后端接口配置");

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/interview/history?limit=${limit}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) throw new Error("获取面试历史失败");
  return response.json() as Promise<InterviewHistoryResponse>;
}

export type CoachOpeningMessageResponse = {
  greeting: string;
  weakness_summary: string | null;
  evidence: string | null;
  focus_today: string;
  cta_type: "new" | "returning";
};

type StreamInterviewChatOptions = {
  token: string;
  message: string;
  signal?: AbortSignal;
  onDelta: (text: string) => void;
  onState?: (state: InterviewProgressState) => void;
  onReport?: (report: InterviewReport) => void;
};

const DEFAULT_ERROR_MESSAGE = "请求失败，请稍后重试";

/** 调用后端统一面试入口，并把 SSE state / delta / report 事件交给 UI 层渲染。 */
export async function streamInterviewChat({
  token,
  message,
  signal,
  onDelta,
  onState,
  onReport,
}: StreamInterviewChatOptions): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) {
    throw new Error("缺少后端接口配置");
  }

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/interview/turn`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(DEFAULT_ERROR_MESSAGE);
  }

  await readSseStream({
    stream: response.body,
    onEvent: (event) => handleSseEvent(event, onDelta, onState, onReport),
  });
}

function handleSseEvent(
  { event, data }: SseEvent,
  onDelta: (text: string) => void,
  onState?: (state: InterviewProgressState) => void,
  onReport?: (report: InterviewReport) => void,
) {
  if (event === "done") return;

  if (event === "state") {
    const payload = parseJsonPayload<InterviewProgressState>(data);
    onState?.(payload);
    return;
  }

  if (event === "delta") {
    const payload = parseJsonPayload<{ text?: string }>(data);
    if (payload.text) onDelta(payload.text);
    return;
  }

  if (event === "report") {
    const payload = parseJsonPayload<InterviewReport>(data);
    onReport?.(payload);
    return;
  }

  if (event === "error") {
    const payload = parseJsonPayload<{ message?: string }>(data);
    throw new Error(payload.message || DEFAULT_ERROR_MESSAGE);
  }
}

/** 返回 Coach 页面所需的用户上下文，判断新老用户。 */
export async function fetchInterviewContext({
  token,
}: {
  token: string;
}): Promise<UserContextResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) throw new Error("缺少后端接口配置");

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/interview/context`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) throw new Error("获取用户信息失败");
  return response.json() as Promise<UserContextResponse>;
}

/** 返回 Coach 页面个性化开场词。 */
export async function fetchCoachOpeningMessage({
  token,
}: {
  token: string;
}): Promise<CoachOpeningMessageResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) throw new Error("缺少后端接口配置");

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/coach/opening-message`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) throw new Error("获取 Coach 开场词失败");
  return response.json() as Promise<CoachOpeningMessageResponse>;
}

/** 放弃当前面试 session，可携带 Coach 收集的上下文预建新 session。失败时静默忽略，不影响 UI。 */
export async function resetInterviewSession({
  token,
  target_role,
  user_background,
}: {
  token: string;
  target_role?: string;
  user_background?: string;
}): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) return;

  const body: Record<string, string> = {};
  if (target_role) body.target_role = target_role;
  if (user_background) body.user_background = user_background;

  try {
    await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/interview/reset`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
  } catch {
    // 网络错误不阻塞 UI 初始化
  }
}

function parseJsonPayload<T>(data: string): T {
  try {
    return JSON.parse(data) as T;
  } catch {
    throw new Error(DEFAULT_ERROR_MESSAGE);
  }
}
