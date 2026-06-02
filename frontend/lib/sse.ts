export type SseEvent = {
  event: string;
  data: string;
};

type ReadSseStreamOptions = {
  stream: ReadableStream<Uint8Array>;
  onEvent: (event: SseEvent) => void;
};

/** 读取 SSE 响应流，兼容 LF/CRLF、chunk 拆分、多事件和多行 data。 */
export async function readSseStream({ stream, onEvent }: ReadSseStreamOptions): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    buffer = emitCompleteEvents(buffer, onEvent);
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    onEvent(parseSseEvent(buffer));
  }
}

/** 异步生成器版本的 SSE 读取器，支持 for await。 */
export async function* readSseStreamGen(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<SseEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() ?? "";

      for (const rawEvent of events) {
        if (rawEvent.trim()) {
          yield parseSseEvent(rawEvent);
        }
      }
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      yield parseSseEvent(buffer);
    }
  } finally {
    reader.releaseLock();
  }
}

function emitCompleteEvents(buffer: string, onEvent: (event: SseEvent) => void): string {
  const events = buffer.split(/\r?\n\r?\n/);
  const remainder = events.pop() ?? "";

  for (const rawEvent of events) {
    if (rawEvent.trim()) {
      onEvent(parseSseEvent(rawEvent));
    }
  }

  return remainder;
}

function parseSseEvent(rawEvent: string): SseEvent {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of rawEvent.split(/\r?\n/)) {
    if (line.startsWith(":")) continue;

    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
      continue;
    }

    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  return {
    event,
    data: dataLines.join("\n"),
  };
}
