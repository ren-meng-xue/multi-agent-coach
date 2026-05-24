import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { streamInterviewChat } from "./interview-chat";

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

  it("读取 SSE delta 并按顺序回调文本", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        makeSseStream(
          'event: delta\ndata: {"text":"你可以"}\n\n' +
            'event: delta\ndata: {"text":"先介绍项目"}\n\n' +
            "event: done\ndata: {}\n\n",
        ),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const chunks: string[] = [];
    await streamInterviewChat({
      token: "test-token",
      messages: [{ role: "user", content: "练后端" }],
      onDelta: (text) => chunks.push(text),
    });

    expect(chunks).toEqual(["你可以", "先介绍项目"]);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/interview/chat",
      expect.objectContaining({
        method: "POST",
        headers: {
          Authorization: "Bearer test-token",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ messages: [{ role: "user", content: "练后端" }] }),
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
      messages: [{ role: "user", content: "练后端" }],
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
        messages: [{ role: "user", content: "练后端" }],
        onDelta: vi.fn(),
      }),
    ).rejects.toThrow("AI 暂时无法响应");
  });

  it("HTTP 失败时抛出通用错误", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));

    await expect(
      streamInterviewChat({
        token: "bad-token",
        messages: [{ role: "user", content: "练后端" }],
        onDelta: vi.fn(),
      }),
    ).rejects.toThrow("请求失败，请稍后重试");
  });
});
