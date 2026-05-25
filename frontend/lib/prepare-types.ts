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
    summary?: string;
    direction?: string;
    message?: string;
    code?: string;
  };
}
