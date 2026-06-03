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
    | "turn_delta" | "turn_state" | "turn_report" | "turn_done"
    | "tool_thinking_start" | "tool_thinking_token" | "tool_thinking_done"
    | "tool_call_start" | "tool_call_done";
  data: {
    node?: string;
    label?: string;
    title?: string;
    text?: string;
    elapsed_ms?: number;
    summary_score?: number;
    candidate_level?: "beginner" | "junior" | "mid" | "senior";
    latent_signals?: string[];
    missing_dimensions?: string[];
    followup_focus?: string;
    chief_tool_calls?: string[];
    assistant_message?: string;
    designed_question?: string;
    designed_category?: string;
    designed_source?: string;
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
    iteration?: number;
    step_id?: string;
    tool_name?: string;
    tool_args_summary?: string;
    tool_result_summary?: string;
    tool_elapsed_ms?: number;
    tool_error?: string;
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
  chiefToolCalls?: string[];
  summaryScore?: number;
  /** designer agent 出题结果，在 chief_think/chief_respond 节点展示 */
  designedQuestion?: string;
  designedCategory?: string;
  designedSource?: string;
  /** research_agent 节点专属：工具思考步骤树 */
  reactSteps?: ReactIteration[];
  /** research_agent 节点专属：ReAct loop 整体状态 */
  reactStatus?: "running" | "done";
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
  chiefToolCalls?: string[];
  /** 节点产出的 AI 回复（ask_question/followup/closing 用准备题库路径时无 LLM token 流，通过此字段补充） */
  assistantMessage?: string;
  /** designer agent 出题结果 */
  designedQuestion?: string;
  designedCategory?: string;
  designedSource?: string;
}

export interface ToolCallStep {
  stepId: string;
  toolName: string;
  argsSummary: string;
  resultSummary?: string;
  elapsedMs?: number;
  error?: string;
  status: "running" | "done" | "error";
}

export interface ReactIteration {
  index: number;
  thinkContent: string;
  thinkStatus: "running" | "done";
  toolCalls: ToolCallStep[];
}