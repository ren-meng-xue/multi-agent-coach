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
  event:
    | "node_start" | "node_token" | "node_done" | "done" | "error"
    | "phase_change"
    | "turn_node_start" | "turn_node_token" | "turn_node_done"
    | "turn_delta" | "turn_state" | "turn_report" | "turn_done";
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
    turn_id?: string;
    stage?: "opening" | "interview" | "closing";
    question_count?: number;
    total_questions?: number;
    overall_score?: number;
    technical_depth?: number;
    quantified_results?: number;
    failure_tradeoffs?: number;
    structure?: number;
    highlights?: string[];
    improvements?: string[];
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
  candidateLevel?: "beginner" | "junior" | "mid" | "senior";
  latentSignals?: string[];
  missingDimensions?: string[];
  followupFocus?: string;
}

export interface InterviewTraceNodeEvent {
  phase: "start" | "token" | "done";
  node: string;
  label?: string;
  text?: string;
  elapsedMs?: number;
  chain?: string[];
  summaryScore?: number;
  candidateLevel?: "beginner" | "junior" | "mid" | "senior";
  latentSignals?: string[];
  missingDimensions?: string[];
  followupFocus?: string;
}
