/** 面试官等待首个流式片段时展示的三点输入状态。 */
export function TypingIndicator() {
  return (
    <span className="inline-flex items-center gap-1 px-1 py-1" aria-label="面试官正在输入">
      <span className="size-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:-0.2s]" />
      <span className="size-1.5 animate-bounce rounded-full bg-zinc-400 [animation-delay:-0.1s]" />
      <span className="size-1.5 animate-bounce rounded-full bg-zinc-400" />
    </span>
  );
}
