import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReportCard } from "./report-card";
import type { InterviewReport } from "@/lib/interview-chat";

const sampleReport: InterviewReport = {
  overall_score: 7.5,
  technical_depth: 4.0,
  quantified_results: 3.0,
  failure_tradeoffs: 4.0,
  structure: 3.5,
  highlights: ["设计清晰", "表达有条理"],
  improvements: ["缺少量化数据", "可补充失败案例"],
};

describe("ReportCard", () => {
  it("渲染综合评分和四个维度分数", () => {
    render(<ReportCard report={sampleReport} />);

    expect(screen.getByText("本轮面试报告")).toBeInTheDocument();
    expect(screen.getByText("7.5")).toBeInTheDocument();
    expect(screen.getByText("/ 10")).toBeInTheDocument();
    expect(screen.getAllByText("4.0 / 5")).toHaveLength(2);
    expect(screen.getByText("3.5 / 5")).toBeInTheDocument();
  });

  it("渲染亮点和改进建议列表", () => {
    render(<ReportCard report={sampleReport} />);

    expect(screen.getByText("设计清晰")).toBeInTheDocument();
    expect(screen.getByText("表达有条理")).toBeInTheDocument();
    expect(screen.getByText("缺少量化数据")).toBeInTheDocument();
    expect(screen.getByText("可补充失败案例")).toBeInTheDocument();
  });

  it("highlights 和 improvements 为空数组时不崩溃", () => {
    render(<ReportCard report={{ ...sampleReport, highlights: [], improvements: [] }} />);
    expect(screen.getByText("本轮面试报告")).toBeInTheDocument();
  });
});
