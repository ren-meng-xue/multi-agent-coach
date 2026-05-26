export interface JDContext {
  company: string;
  role: string;
  key_skills: string[];
  focus_areas: string[];
  difficulty: "easy" | "medium" | "hard" | "faang";
}

export interface PreparedQuestion {
  id: number;
  question: string;
  category: "technical" | "behavioral" | "system_design";
  focus_area: string;
  priority: number;
}

export interface PrepareSSEEvent {
  event: "node_start" | "node_token" | "node_done" | "done" | "error";
  data: {
    node?: string;
    label?: string;
    text?: string;
    elapsed_ms?: number;
    chain?: string[];
    need_direction?: boolean;
    prepared_questions?: PreparedQuestion[];
    jd_context?: JDContext;
    summary?: string;
    direction?: string;
    message?: string;
    code?: string;
  };
}

export type TraceNodeStatus = "pending" | "running" | "done";

export interface TraceNodeData {
  id: string;
  label: string;
  title?: string;
  status: TraceNodeStatus;
  tokens: string;
  elapsedMs?: number;
}

export interface InterviewTraceNodeEvent {
  phase: "start" | "token" | "done";
  node: string;
  label?: string;
  text?: string;
  elapsedMs?: number;
  chain?: string[];
  summaryScore?: number;
}
