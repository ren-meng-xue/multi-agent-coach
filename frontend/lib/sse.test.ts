import { describe, expect, it } from "vitest";
import { readSseStream, type SseEvent } from "./sse";

function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

describe("readSseStream", () => {
  it("读取 LF 分隔的多个 SSE 事件", async () => {
    const events: SseEvent[] = [];

    await readSseStream({
      stream: makeStream([
        'event: delta\ndata: {"text":"你可以"}\n\n' +
          'event: done\ndata: {}\n\n',
      ]),
      onEvent: (event) => events.push(event),
    });

    expect(events).toEqual([
      { event: "delta", data: '{"text":"你可以"}' },
      { event: "done", data: "{}" },
    ]);
  });

  it("兼容 CRLF 分隔的 SSE 事件", async () => {
    const events: SseEvent[] = [];

    await readSseStream({
      stream: makeStream([
        'event: delta\r\ndata: {"text":"请"}\r\n\r\n' +
          'event: delta\r\ndata: {"text":"详细描述"}\r\n\r\n',
      ]),
      onEvent: (event) => events.push(event),
    });

    expect(events).toEqual([
      { event: "delta", data: '{"text":"请"}' },
      { event: "delta", data: '{"text":"详细描述"}' },
    ]);
  });

  it("兼容一个 SSE 事件被拆到多个网络 chunk", async () => {
    const events: SseEvent[] = [];

    await readSseStream({
      stream: makeStream(["event: del", 'ta\ndata: {"text":"拆', '分"}\n\n']),
      onEvent: (event) => events.push(event),
    });

    expect(events).toEqual([{ event: "delta", data: '{"text":"拆分"}' }]);
  });

  it("兼容一个 chunk 中包含多个事件和末尾残留事件", async () => {
    const events: SseEvent[] = [];

    await readSseStream({
      stream: makeStream([
        'event: delta\ndata: {"text":"A"}\n\n' +
          'event: delta\ndata: {"text":"B"}',
      ]),
      onEvent: (event) => events.push(event),
    });

    expect(events).toEqual([
      { event: "delta", data: '{"text":"A"}' },
      { event: "delta", data: '{"text":"B"}' },
    ]);
  });

  it("保留多行 data 并忽略注释行", async () => {
    const events: SseEvent[] = [];

    await readSseStream({
      stream: makeStream(["event: note\n: keepalive\ndata: 第一行\ndata: 第二行\n\n"]),
      onEvent: (event) => events.push(event),
    });

    expect(events).toEqual([{ event: "note", data: "第一行\n第二行" }]);
  });
});
