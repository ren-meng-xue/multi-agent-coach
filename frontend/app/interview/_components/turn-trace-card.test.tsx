import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { TurnTraceCard } from "./turn-trace-card";

describe("TurnTraceCard", () => {
  it("renders running state with turn index", () => {
    render(
      <TurnTraceCard
        status="running"
        nodes={[
          { id: "master", label: "MASTER", status: "running", tokens: "" },
        ]}
        turnIndex={1}
      />,
    );
    expect(screen.getByText(/本轮分析中/)).toBeInTheDocument();
    expect(screen.getByText(/第 1 轮/)).toBeInTheDocument();
  });

  it("renders done state with summary score", () => {
    render(
      <TurnTraceCard
        status="done"
        nodes={[
          { id: "master", label: "MASTER", status: "done", tokens: "评估并追问", elapsedMs: 120 },
          { id: "evaluator", label: "评估", status: "done", tokens: "·覆盖CAP", elapsedMs: 280 },
          { id: "followup", label: "面试官 · 追问", status: "done", tokens: "", elapsedMs: 950 },
        ]}
        turnIndex={2}
        summaryScore={7.4}
      />,
    );
    expect(screen.getByText(/本轮分析完成/)).toBeInTheDocument();
    expect(screen.getByText(/7\.4/)).toBeInTheDocument();
  });
});
