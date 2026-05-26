import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { TraceNode } from "./trace-node";

test("pending 状态显示灰色圆圈", () => {
  render(
    <TraceNode
      id="master"
      label="MASTER"
      title="识别方向"
      status="pending"
      tokens=""
    />
  );
  expect(screen.getByTestId("trace-node-master")).toBeInTheDocument();
  expect(screen.getByTestId("trace-status-pending")).toBeInTheDocument();
});

test("running 状态显示动画圆圈", () => {
  render(
    <TraceNode
      id="master"
      label="MASTER"
      title="识别方向"
      status="running"
      tokens="检查用户档案"
    />
  );
  expect(screen.getByTestId("trace-status-running")).toBeInTheDocument();
  expect(screen.getByText("检查用户档案")).toBeInTheDocument();
});

test("非 master 节点 running 时显示 token 内容", () => {
  render(
    <TraceNode
      id="memory_search"
      label="记忆检索"
      title="读取历史"
      status="running"
      tokens="正在查询数据库"
    />
  );
  expect(screen.getByTestId("trace-status-running")).toBeInTheDocument();
  expect(screen.getByText("正在查询数据库")).toBeInTheDocument();
});

test("done 状态显示绿色勾 + 耗时", () => {
  render(
    <TraceNode
      id="master"
      label="MASTER"
      title="识别方向"
      status="done"
      tokens="检查完毕"
      elapsedMs={62}
    />
  );
  expect(screen.getByTestId("trace-status-done")).toBeInTheDocument();
  expect(screen.getByText("62ms")).toBeInTheDocument();
});
