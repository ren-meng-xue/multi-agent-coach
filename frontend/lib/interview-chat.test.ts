import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { streamInterviewChat, resetInterviewSession } from "./interview-chat";

function makeSseStream(text: string): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
}

describe("streamInterviewChat", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("调用统一 turn 入口，读取 state 与 delta 事件", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        makeSseStream(
          'event: state\ndata: {"stage":"interview","question_count":1,"total_questions":5}\n\n' +
            'event: delta\ndata: {"text":"你可以"}\n\n' +
            'event: delta\ndata: {"text":"先介绍项目"}\n\n' +
            "event: done\ndata: {}\n\n",
        ),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const chunks: string[] = [];
    const states: unknown[] = [];
    await streamInterviewChat({
      token: "test-token",
      message: "练后端",
      onDelta: (text) => chunks.push(text),
      onState: (state) => states.push(state),
    });

    expect(chunks).toEqual(["你可以", "先介绍项目"]);
    expect(states).toEqual([{ stage: "interview", question_count: 1, total_questions: 5 }]);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/interview/turn",
      expect.objectContaining({
        method: "POST",
        headers: {
          Authorization: "Bearer test-token",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: "练后端" }),
      }),
    );
  });

  it("兼容 CRLF 分隔的 SSE 事件", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          makeSseStream(
            'event: delta\r\ndata: {"text":"请"}\r\n\r\n' +
              'event: delta\r\ndata: {"text":"详细描述"}\r\n\r\n' +
              "event: done\r\ndata: {}\r\n\r\n",
          ),
          { status: 200 },
        ),
      ),
    );

    const chunks: string[] = [];
    await streamInterviewChat({
      token: "test-token",
      message: "练后端",
      onDelta: (text) => chunks.push(text),
    });

    expect(chunks).toEqual(["请", "详细描述"]);
  });

  it("收到 error 事件时抛出用户可见错误", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          makeSseStream('event: error\ndata: {"message":"AI 暂时无法响应"}\n\n'),
          { status: 200 },
        ),
      ),
    );

    await expect(
      streamInterviewChat({
        token: "test-token",
        message: "练后端",
        onDelta: vi.fn(),
      }),
    ).rejects.toThrow("AI 暂时无法响应");
  });

  it("HTTP 失败时抛出通用错误", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));

    await expect(
      streamInterviewChat({
        token: "bad-token",
        message: "练后端",
        onDelta: vi.fn(),
      }),
    ).rejects.toThrow("请求失败，请稍后重试");
  });

  it("收到 report 事件时调用 onReport 回调", async () => {
    const reportPayload = {
      overall_score: 7.5,
      technical_depth: 4.0,
      quantified_results: 3.0,
      failure_tradeoffs: 4.0,
      structure: 3.5,
      highlights: ["表达清晰"],
      improvements: ["可补充量化数据"],
    };

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          makeSseStream(
            `event: state\ndata: {"stage":"closing","question_count":5,"total_questions":5}\n\n` +
              `event: report\ndata: ${JSON.stringify(reportPayload)}\n\n` +
              `event: done\ndata: {}\n\n`,
          ),
          { status: 200 },
        ),
      ),
    );

    const reports: unknown[] = [];
    await streamInterviewChat({
      token: "test-token",
      message: "第五题",
      onDelta: vi.fn(),
      onReport: (report) => reports.push(report),
    });

    expect(reports).toHaveLength(1);
    expect(reports[0]).toMatchObject({ overall_score: 7.5, highlights: ["表达清晰"] });
  });
});

describe("resetInterviewSession", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("调用 reset 端点并传入 Bearer token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await resetInterviewSession({ token: "test-token" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/interview/reset",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
        }),
      }),
    );
  });

  it("HTTP 失败时静默忽略（不抛错）", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 500 })));

    await expect(resetInterviewSession({ token: "test-token" })).resolves.toBeUndefined();
  });
});

describe("fetchInterviewContext", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("调用 GET /context 并返回用户上下文", async () => {
    const payload = {
      is_returning: true,
      target_role: "AI Agent 工程师",
      target_company: null,
      user_background: "LangGraph 系统",
      session_count: 7,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { fetchInterviewContext } = await import("./interview-chat");
    const result = await fetchInterviewContext({ token: "test-token" });

    expect(result.is_returning).toBe(true);
    expect(result.target_role).toBe("AI Agent 工程师");
    expect(result.session_count).toBe(7);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/interview/context",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
  });

  it("HTTP 失败时抛出错误", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    const { fetchInterviewContext } = await import("./interview-chat");
    await expect(fetchInterviewContext({ token: "bad" })).rejects.toThrow("获取用户信息失败");
  });
});

describe("resetInterviewSession with context", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("携带 target_role 时发送 JSON body", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { resetInterviewSession } = await import("./interview-chat");
    await resetInterviewSession({
      token: "test-token",
      target_role: "前端工程师",
      user_background: "Vue 项目",
    });

    const call = fetchMock.mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body.target_role).toBe("前端工程师");
    expect(body.user_background).toBe("Vue 项目");
  });

  it("不携带 target_role 时 body 为空对象", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { resetInterviewSession } = await import("./interview-chat");
    await resetInterviewSession({ token: "test-token" });

    const call = fetchMock.mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body).toEqual({});
  });
});
