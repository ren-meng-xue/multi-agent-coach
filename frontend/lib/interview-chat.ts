import { readSseStream, type SseEvent } from "./sse";
import type {
  InterviewTraceNodeEvent,
  JDContext,
  PreparedQuestion,
  TraceNodeData,
} from "./prepare-types";

export type InterviewChatTextMessage = {
  role: "user" | "assistant";
  content: string;
};

export type InterviewPrepareTracePayload = {
  status: "running" | "done" | "waiting_direction";
  nodes: TraceNodeData[];
  questions: PreparedQuestion[];
  summary: string;
  direction?: string;
  jdContext?: JDContext;
};

export type InterviewTurnTracePayload = {
  status: "running" | "done";
  nodes: TraceNodeData[];
  chain?: string[];
  summaryScore?: number;
  turnIndex: number;
  isOpening?: boolean;
  error?: string;
};

export type InterviewPrepareTraceMessage = {
  role: "trace";
  kind: "prepare";
  payload: InterviewPrepareTracePayload;
};

export type InterviewTurnTraceMessage = {
  role: "trace";
  kind: "turn";
  id: string;
  payload: InterviewTurnTracePayload;
};

export type InterviewChatMessage =
  | InterviewChatTextMessage
  | InterviewPrepareTraceMessage
  | InterviewTurnTraceMessage;

export function isTextMessage(m: InterviewChatMessage): m is InterviewChatTextMessage {
  return m.role === "user" || m.role === "assistant";
}

export function isPrepareTraceMessage(m: InterviewChatMessage): m is InterviewPrepareTraceMessage {
  return m.role === "trace" && m.kind === "prepare";
}

export function isTurnTraceMessage(m: InterviewChatMessage): m is InterviewTurnTraceMessage {
  return m.role === "trace" && m.kind === "turn";
}

export const INTERVIEW_NODE_TITLES: Record<string, string> = {
  master: "分析表现，规划下一步",
  evaluator: "多维深度评估",
  followup: "生成追问逻辑",
  ask_question: "抽取下一道题",
};

export const INTERVIEW_NODE_LABELS: Record<string, string> = {
  master: "调度",
  evaluator: "评估官",
  followup: "面试官",
  ask_question: "出题官",
};

export const PREPARE_NODE_TITLES: Record<string, string> = {
  master: "识别方向，启动准备",
  memory_search: "读取你的历史表现",
  jd_analysis: "构建考点地图",
  question_gen: "定制专属题目",
};

/** 格式化 Trace 节点的 tokens，过滤 JSON 并美化输出。 */
export function formatTraceTokens(id: string, tokens: string): string {
  if (!tokens) return "(无详细信息)";

  // 出题节点特殊处理：提取 JSON 中的 question 字段
  if (id === "question_gen" || id === "ask_question") {
    const robustPattern = /["']?question["']?\s* : \s*["']((?:[^"'\\]|\\?[\s\S])*?)(?:["']|$)/gi;
    // 注意：上面的正则空格是为了匹配，实际代码中可能更紧凑
    const matches = Array.from(tokens.matchAll(/["']?question["']?\s*:\s*["']((?:[^"'\\]|\\?[\s\S])*?)(?:["']|$)/gi));
    const questions = matches
      .map((m) => m[1].replace(/\\"/g, '"').replace(/\\n/g, " ").trim())
      .filter((q) => q.length > 2);

    if (questions.length > 0) {
      return questions.map((q) => `→ ${q}`).join("\n    ");
    }
  }

  // 其他节点：过滤 JSON 标记，保留普通文本
  return tokens
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => {
      return (
        line &&
        !line.startsWith("[") &&
        !line.startsWith("{") &&
        !line.includes('": "') &&
        !line.startsWith("}") &&
        !line.startsWith("]")
      );
    })
    .map((line) => line.replace(/^[•\-]\s*/, "→ "))
    .join("\n    ");
}

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
  target_company: string | null;
  user_background: string | null;
  session_count: number;
  last_session_id: string | null;
  resume_filename: string | null;
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

export type ActiveMessageItem = {
  role: string;
  content: string;
};

export type ActiveSessionResponse = {
  session_id?: string;
  target_role?: string;
  target_company?: string;
  user_background?: string;
  stage?: "opening" | "interview" | "closing";
  question_count?: number;
  total_questions?: number;
  followup_count?: number;
  messages: ActiveMessageItem[];
  report?: InterviewReport | null;
};

/** 获取当前进行中（in_progress）的活动会话及消息历史。 */
export async function fetchActiveInterviewSession({
  token,
}: {
  token: string;
}): Promise<ActiveSessionResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) throw new Error("缺少后端接口配置");

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/interview/active`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) throw new Error("获取活动面试会话失败");
  return response.json() as Promise<ActiveSessionResponse>;
}

export type CoachOpeningMessageResponse = {
  greeting: string;
  weakness_summary: string | null;
  evidence: string | null;
  focus_today: string;
  cta_type: "new" | "returning";
  // 第五步「教练 Agent + 共享记忆层」预留：默认空数组，本次不渲染
  long_memory_hints?: string[];
  hobby_hints?: string[];
};

type StreamInterviewChatOptions = {
  token: string;
  message: string;
  preparedQuestions?: PreparedQuestion[];
  jdContext?: JDContext | null;
  targetRole?: string;
  useQABank?: boolean;
  signal?: AbortSignal;
  onDelta: (text: string) => void;
  onState?: (state: InterviewProgressState) => void;
  onReport?: (report: InterviewReport) => void;
  onTraceNode?: (ev: InterviewTraceNodeEvent) => void;
};

const DEFAULT_ERROR_MESSAGE = "请求失败，请稍后重试";

/** 调用后端统一面试入口，并把 SSE state / delta / report 事件交给 UI 层渲染。 */
export async function streamInterviewChat({
  token,
  message,
  preparedQuestions,
  jdContext,
  targetRole,
  useQABank,
  signal,
  onDelta,
  onState,
  onReport,
  onTraceNode,
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
    body: JSON.stringify({
      message,
      prepared_questions: preparedQuestions,
      jd_context: jdContext,
      target_role: targetRole,
      use_qa_bank: useQABank ?? false,
    }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(DEFAULT_ERROR_MESSAGE);
  }

  await readSseStream({
    stream: response.body,
    onEvent: (event) => handleSseEvent(event, onDelta, onState, onReport, onTraceNode),
  });
}

function handleSseEvent(
  { event, data }: SseEvent,
  onDelta: (text: string) => void,
  onState?: (state: InterviewProgressState) => void,
  onReport?: (report: InterviewReport) => void,
  onTraceNode?: (ev: InterviewTraceNodeEvent) => void,
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

  if (event === "node_start" || event === "node_token" || event === "node_done") {
    const payload = parseJsonPayload<{
      node: string;
      label?: string;
      text?: string;
      elapsed_ms?: number;
      chain?: string[];
      summary_score?: number;
    }>(data);
    const phase = event === "node_start" ? "start" : event === "node_token" ? "token" : "done";
    onTraceNode?.({
      phase,
      node: payload.node,
      label: payload.label,
      text: payload.text,
      elapsedMs: payload.elapsed_ms,
      chain: payload.chain,
      summaryScore: payload.summary_score,
    });
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

  const res = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/interview/reset`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Reset failed with HTTP status: ${res.status}`);
  }
}

function parseJsonPayload<T>(data: string): T {
  try {
    return JSON.parse(data) as T;
  } catch {
    throw new Error(DEFAULT_ERROR_MESSAGE);
  }
}

/** 启动准备流水线（支持多源 JD，流式 SSE 返回）。 */
export async function* startPrepareStreamFetch(params: {
  token: string;
  userDirection?: string;
  userBackground?: string;
  jdText?: string;
  jdUrl?: string;
  jdFile?: File;
  signal?: AbortSignal;
}): AsyncGenerator<import("./prepare-types").PrepareSSEEvent, void, unknown> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const form = new FormData();
  if (params.userDirection) form.append("user_direction", params.userDirection);
  if (params.userBackground) form.append("user_background", params.userBackground);
  if (params.jdText) form.append("jd_text", params.jdText);
  if (params.jdUrl) form.append("jd_url", params.jdUrl);
  if (params.jdFile) form.append("jd_file", params.jdFile);

  const resp = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/prepare/start`, {
    method: "POST",
    headers: { Authorization: `Bearer ${params.token}` },
    body: form,
    signal: params.signal,
  });

  yield* _readPrepareStream(resp);
}

/** 恢复准备流水线（需要向用户追问方向场景）。 */
export async function* resumePrepareStreamFetch(params: {
  token: string;
  direction: string;
  userBackground?: string;
  jdText?: string;
  weakAreas?: string;
  starStories?: string;
  signal?: AbortSignal;
}): AsyncGenerator<import("./prepare-types").PrepareSSEEvent, void, unknown> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
  const form = new FormData();
  form.append("direction", params.direction);
  if (params.userBackground) form.append("user_background", params.userBackground);
  if (params.jdText) form.append("jd_text", params.jdText);
  if (params.weakAreas) form.append("weak_areas", params.weakAreas);
  if (params.starStories) form.append("star_stories", params.starStories);

  const resp = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/prepare/resume`, {
    method: "POST",
    headers: { Authorization: `Bearer ${params.token}` },
    body: form,
    signal: params.signal,
  });

  yield* _readPrepareStream(resp);
}

/** 内部通用的 SSE 读取生成器 */
async function* _readPrepareStream(
  resp: Response
): AsyncGenerator<import("./prepare-types").PrepareSSEEvent, void, unknown> {
  if (!resp.ok || !resp.body) throw new Error("Prepare stream failed");

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine.startsWith("data: ")) {
          try {
            yield JSON.parse(trimmedLine.slice(6)) as import("./prepare-types").PrepareSSEEvent;
          } catch {
            // ignore parsing error
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

type AppRouter = {
  push: (href: string) => void;
  replace: (href: string) => void;
};

export type EnterInterviewRoomContext = {
  target_role?: string;
  user_background?: string;
  jd_text?: string;
  jd_url?: string;
  use_qa_bank?: boolean;
};

/** 统一封装从任意入口进入 /interview 的流程：写 sessionStorage + reset 后台 session + push。
 *  reset 失败仅 warn，不阻塞跳转 —— 路由守卫层会兜底处理无 active session 的情况。 */
export async function enterInterviewRoom({
  getToken,
  router,
  context,
}: {
  getToken: () => Promise<string | null>;
  router: AppRouter;
  context: EnterInterviewRoomContext;
}): Promise<void> {
  sessionStorage.setItem("interview_context", JSON.stringify(context));

  const token = await getToken();
  if (token) {
    try {
      await resetInterviewSession({
        token,
        target_role: context.target_role,
        user_background: context.user_background,
      });
    } catch (err) {
      console.warn("enterInterviewRoom: reset failed, proceeding anyway", err);
    }
  }

  router.push("/interview");
}
