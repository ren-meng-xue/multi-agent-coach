"use client";

import { useEffect, useRef, useState, KeyboardEvent, ClipboardEvent } from "react";
import { Send, Plus, X, FileText, Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Attachment {
  id: string;
  name: string;
  size: number;
  type: string;
  url: string; // 本地 blob 预览 URL
  isUploading?: boolean; // 新增：是否处于正在上传的 loading 状态
}

interface ChatInputProps {
  onSend: (content: string) => void;
  isStreaming: boolean;
  onUploadFile?: (file: File) => void;
}

/** 格式化字节数为可读字符串 */
function formatBytes(bytes: number, decimals = 2) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

/** 根据文件名与类型获取对应的定制图标背景色及标签类型文字 */
function getFileConfig(fileName: string, fileType: string) {
  const ext = fileName.split(".").pop()?.toLowerCase() || "";

  // 1. PDF 格式：红色底色
  if (ext === "pdf" || fileType === "application/pdf") {
    return {
      bgColor: "bg-[#ef4444] shadow-red-500/10 dark:bg-red-600",
      label: "PDF",
    };
  }

  // 2. DOCX / DOC 格式：蓝色底色
  if (
    ext === "docx" ||
    ext === "doc" ||
    fileType.includes("word") ||
    fileType.includes("officedocument.wordprocessingml.document")
  ) {
    return {
      bgColor: "bg-[#3b82f6] shadow-blue-500/10 dark:bg-blue-600",
      label: "文档",
    };
  }

  // 3. Excel 格式：绿色底色
  if (
    ext === "xlsx" ||
    ext === "xls" ||
    fileType.includes("excel") ||
    fileType.includes("spreadsheetml.sheet")
  ) {
    return {
      bgColor: "bg-emerald-500 shadow-emerald-500/10 dark:bg-emerald-600",
      label: "表格",
    };
  }

  // 4. PPT 格式：橙色底色
  if (
    ext === "pptx" ||
    ext === "ppt" ||
    fileType.includes("powerpoint") ||
    fileType.includes("presentationml.presentation")
  ) {
    return {
      bgColor: "bg-orange-500 shadow-orange-500/10 dark:bg-orange-600",
      label: "演示文稿",
    };
  }

  // 5. 文本 格式：灰色底色
  if (ext === "txt" || fileType.startsWith("text/")) {
    return {
      bgColor: "bg-zinc-500 shadow-zinc-500/10",
      label: "文本",
    };
  }

  // 6. 压缩包 格式：紫色底色
  if (
    ["zip", "rar", "7z", "tar", "gz"].includes(ext) ||
    fileType.includes("zip") ||
    fileType.includes("compressed")
  ) {
    return {
      bgColor: "bg-purple-500 shadow-purple-500/10",
      label: "压缩包",
    };
  }

  // 默认其他类型
  return {
    bgColor: "bg-slate-500 shadow-slate-500/10",
    label: "文件",
  };
}

/**
 * AI模拟面试舱的独立输入组件
 * 封装了：
 * 1. Textarea 动态高度自适应（最高 160px）及极细滚动太美化
 * 2. 页面进入自动聚焦光标一闪一闪
 * 3. 回车发送，Shift + Enter 换行
 * 4. 文件拖动/剪贴板粘贴一键捕获上传 (+) 
 * 5. 完全对齐 ChatGPT 的附件预览列表（支持单行横向滚动，卡片 shrink-0 不变形，定制 PDF 红色/Word 蓝色底色）
 * 6. 极致脱离输入框的全局 Fixed 黑色 Tooltip，彻底打破 overflow-x-auto 容器截断及边框层级限制
 * 7. 【NEW】抛弃输入框内生硬占位符文案，使用每个附件独立的“旋转 Loading”半透明卡片占位交互，优雅模拟上传过程
 * 8. 上传过程中输入框、上传按钮与发送按钮禁用状态，以及提示词保持原始简洁
 * 9. 万能高保真文件预览浮层（图片全屏磨砂、PDF 在线 iframe 阅读、Office 大名片及本地下载）
 */
export function ChatInput({ onSend, isStreaming, onUploadFile }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [previewAttachment, setPreviewAttachment] = useState<Attachment | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const isComposingRef = useRef(false);

  // 全局 Fixed 悬浮 Tooltip 状态，用于脱离 DOM 容器限制，自由飘浮于输入框上方外界
  const [globalTooltip, setGlobalTooltip] = useState<{
    visible: boolean;
    text: string;
    x: number;
    y: number;
  }>({ visible: false, text: "", x: 0, y: 0 });

  // 1. 输入字数变化时，动态计算并调整 textarea 高度
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [value]);

  // 2. 组件加载后自动聚焦光标一闪一闪
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // 【NEW】全局监听键盘 Esc 键，以便在开启图片/PDF/文件名片预览大浮层时，支持一键按 Esc 键安全退出关闭
  useEffect(() => {
    function handleGlobalKeyDown(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape" && previewAttachment !== null) {
        setPreviewAttachment(null);
      }
    }

    if (previewAttachment !== null) {
      window.addEventListener("keydown", handleGlobalKeyDown);
    }

    return () => {
      window.removeEventListener("keydown", handleGlobalKeyDown);
    };
  }, [previewAttachment]);

  // 3. 卸载时清理所有遗留的 Blob 预览 URL，避免内存泄漏
  useEffect(() => {
    return () => {
      attachments.forEach((att) => {
        if (att.url.startsWith("blob:")) {
          URL.revokeObjectURL(att.url);
        }
      });
    };
  }, [attachments]);

  // 4. 回车发送，Shift + Enter 换行，避开输入法（IME）确认确认候选字的回车
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // 只有在非输入法合成状态且没有按下 Shift 键时，才触发回车发送
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !isComposingRef.current
    ) {
      event.preventDefault();
      const form = event.currentTarget.form;
      if (form) {
        form.requestSubmit();
      }
    }
  }

  // 5. 统一处理选中的文件：一经选中，瞬间往 attachments 中塞入带 isUploading: true 的半透明 loading 占位卡片，模拟 800ms 上传延迟
  function handleFile(file: File) {
    setIsUploading(true);

    // 无论什么文件，一律生成本地临时 Blob URL
    const blobUrl = URL.createObjectURL(file);
    const tempId = Math.random().toString(36).substring(2, 9);

    // 立即塞入半透明的 Loading 状态临时卡片
    const tempAttachment: Attachment = {
      id: tempId,
      name: file.name,
      size: file.size,
      type: file.type,
      url: blobUrl,
      isUploading: true,
    };

    setAttachments((current) => [...current, tempAttachment]);

    setTimeout(() => {
      // 800ms 模拟上传结束，原地替换该卡片为正常状态
      setAttachments((current) =>
        current.map((att) =>
          att.id === tempId ? { ...att, isUploading: false } : att
        )
      );
      setIsUploading(false);

      // 触发外部自定义上传钩子（若存在）
      if (onUploadFile) {
        onUploadFile(file);
      }
    }, 800);
  }

  // 6. 删除特定附件并释放内存
  function removeAttachment(id: string) {
    setAttachments((current) => {
      const target = current.find((att) => att.id === id);
      if (target && target.url.startsWith("blob:")) {
        URL.revokeObjectURL(target.url);
      }
      return current.filter((att) => att.id !== id);
    });
  }

  // 7. 粘贴事件监听：捕获剪贴板中的文件直接生成预览
  function handlePaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const items = event.clipboardData?.items;
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) {
          event.preventDefault();
          handleFile(file);
          break;
        }
      }
    }
  }

  // 8. 表单提交回调
  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = value.trim();

    // 如果既没有字，也没有任何附件，则不允许发送
    if (!content && attachments.length === 0) return;
    if (isStreaming || isUploading) return;

    // 触发发送
    onSend(content);
    setValue("");

    // 发送后自动清理并释放附件状态
    attachments.forEach((att) => {
      if (att.url.startsWith("blob:")) {
        URL.revokeObjectURL(att.url);
      }
    });
    setAttachments([]);
  }

  // 9. 全局 Tooltip 弹出定位计算函数
  function showTooltip(text: string, e: React.MouseEvent<HTMLElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    setGlobalTooltip({
      visible: true,
      text,
      x: rect.left + rect.width / 2, // 水平居中
      y: rect.top - 8,              // 元素上方 8px
    });
  }

  function hideTooltip() {
    setGlobalTooltip((prev) => ({ ...prev, visible: false }));
  }

  return (
    <>
      <form
        aria-label="面试输入栏"
        className="sticky bottom-0 z-20 flex shrink-0 flex-col border-t border-zinc-200/50 bg-zinc-50/60 px-5 py-4 backdrop-blur-md dark:border-zinc-800/40 dark:bg-[#121212]/60"
        onSubmit={handleSubmit}
      >
        {/* 复合高级输入框容器 - 增加常驻的轻微品牌色边框（#534AB7/25）与背景调性，确保非聚焦时也具备色彩辨识度 */}
        <div className="relative flex flex-col w-full rounded-2xl border border-[#534AB7]/25 bg-white shadow-[0_8px_30px_rgba(83,74,183,0.06)] focus-within:border-[#534AB7]/60 focus-within:ring-4 focus-within:ring-[#534AB7]/10 dark:border-[#534AB7]/30 dark:bg-[#1a1a1a] dark:shadow-[0_8px_40px_rgba(0,0,0,0.4)] transition-all duration-300 p-2">
          
          {/* 完全对齐 ChatGPT 的附件卡片预览列表 - 支持单行横向滚动与极细美化滚动条 */}
          {attachments.length > 0 && (
            <div className="flex flex-row items-center gap-3 px-2.5 pt-1.5 pb-2 border-b border-zinc-100/40 dark:border-zinc-800/20 mb-2 overflow-x-auto whitespace-nowrap shrink-0 [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-thumb]:bg-zinc-200 dark:[&::-webkit-scrollbar-thumb]:bg-zinc-800 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-track]:bg-transparent">
              {attachments.map((att) => {
                // 双保险判定是否为图片：支持 MIME 类型检测，以及文件名后缀正则比对，彻底防范浏览器 MIME 缺失 Bug
                const isImage = att.type.startsWith("image/") || 
                                /\.(jpg|jpeg|png|gif|webp|bmp|ico|svg)$/i.test(att.name);
                const fileConfig = getFileConfig(att.name, att.type);

                // A. 如果该文件处于正在模拟上传的 Loading 状态下：
                if (att.isUploading) {
                  return (
                    <div key={att.id} className="relative shrink-0">
                      <div className="relative flex h-14 items-center gap-2.5 rounded-xl border border-zinc-150 bg-zinc-50/50 px-3 pr-4 dark:border-white/5 dark:bg-zinc-800/20 min-w-[160px] max-w-[240px] select-none opacity-70">
                        {/* 左侧：精致的旋转 Loading 圈圈 */}
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-500">
                          <Loader2 className="size-4 animate-spin text-[#534AB7] dark:text-[#6359e8]" />
                        </div>
                        {/* 右侧：半透明的文件名和带呼吸闪烁动效的“正在上传...” */}
                        <div className="flex flex-col min-w-0 flex-1 pr-1">
                          <span className="truncate text-xs font-semibold text-zinc-400 dark:text-zinc-500">
                            {att.name}
                          </span>
                          <span className="text-[10px] text-zinc-400 font-medium mt-0.5 animate-pulse">
                            正在上传...
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                }

                // B. 上传完成后展现正常状态的文档/图片卡片（包含右上角黑底白叉和全局 Tooltip 悬浮）
                return (
                  <div key={att.id} className="relative shrink-0">
                    
                    {/* 右上角删除按钮：纯正黑底白叉，具有 z-30 最高置顶。触发时立刻关闭 Tooltip 避免残留 */}
                    <div className="absolute -top-1.5 -right-1.5 z-30">
                      <button
                        type="button"
                        aria-label="删除附件"
                        onClick={(e) => {
                          e.stopPropagation();
                          e.preventDefault();
                          hideTooltip(); // 删除后立即彻底隐藏
                          removeAttachment(att.id);
                        }}
                        onMouseEnter={(e) => showTooltip("移除文件", e)}
                        onMouseLeave={hideTooltip}
                        className="size-5 bg-black text-white hover:bg-zinc-800 rounded-full flex items-center justify-center transition-all shadow-md active:scale-95 border border-white/10 dark:bg-white dark:text-black dark:hover:bg-zinc-200 cursor-pointer"
                      >
                        <X className="size-3" />
                      </button>
                    </div>

                    {/* 卡片主体容器：仅在非图片类型文件悬浮时触发文件名的全局 Tooltip */}
                    <div 
                      onMouseEnter={(e) => {
                        if (!isImage) {
                          showTooltip(att.name, e);
                        }
                      }}
                      onMouseLeave={hideTooltip}
                      className="relative"
                    >
                      {isImage ? (
                        // 图片缩略图预览卡片 (支持点击全屏放大)
                        <div 
                          onClick={() => setPreviewAttachment(att)}
                          className="relative size-14 rounded-xl border border-zinc-150 overflow-hidden dark:border-white/10 bg-zinc-50 dark:bg-zinc-900 cursor-pointer shadow-[0_2px_8px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] transition-all duration-250 hover:scale-[1.02]"
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={att.url}
                            alt={att.name}
                            className="size-full object-cover hover:opacity-95 transition-opacity"
                          />
                        </div>
                      ) : (
                        // 文档/各种类型文件预览卡片
                        <div 
                          onClick={() => setPreviewAttachment(att)}
                          className="relative flex h-14 items-center gap-2.5 rounded-xl border border-zinc-200/80 bg-zinc-50/60 px-3 pr-4 dark:border-white/10 dark:bg-zinc-800/40 min-w-[160px] max-w-[240px] cursor-pointer hover:bg-zinc-100/70 dark:hover:bg-zinc-800/70 shadow-[0_2px_8px_rgba(0,0,0,0.04)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.08)] transition-all duration-250 hover:scale-[1.01]"
                        >
                          <div className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg text-white shadow-sm transition-transform", fileConfig.bgColor)}>
                            <FileText className="size-4" />
                          </div>
                          <div className="flex flex-col min-w-0 flex-1 pr-1 select-none">
                            <span className="truncate text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                              {att.name}
                            </span>
                            <span className="text-[10px] text-zinc-400 font-medium mt-0.5">
                              {fileConfig.label}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* 底部输入与按钮排版区 */}
          <div className="flex min-h-[32px] w-full items-end gap-2">
            {/* 上传文件按钮与微动效 Tooltip */}
            <div className="flex items-center justify-center shrink-0 mb-[2px]">
              <Button
                type="button"
                aria-label="上传文件"
                size="icon"
                variant="ghost"
                className="size-8 rounded-xl text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-[#30302d] dark:hover:text-zinc-50"
                disabled={isStreaming || isUploading}
                onClick={() => {
                  const fileInput = document.getElementById("file-upload-input");
                  fileInput?.click();
                }}
                onMouseEnter={(e) => showTooltip("上传文件", e)}
                onMouseLeave={hideTooltip}
              >
                <Plus className="size-4" />
              </Button>
            </div>
            {/* 去掉过严的格式限制，支持各种类型文件 */}
            <input
              id="file-upload-input"
              type="file"
              className="hidden"
              accept="image/*,.pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.txt,.zip,.rar,.7z"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  handleFile(file);
                }
              }}
              disabled={isStreaming || isUploading}
              suppressHydrationWarning
            />

            {/* 动态自动展开的 TextArea 区域：上传期间输入框处于禁用状态，placeholder保持干净清爽 */}
            <textarea
              ref={textareaRef}
              aria-label="输入面试练习内容"
              autoComplete="off"
              className="flex-1 min-h-[32px] max-h-[160px] resize-none bg-transparent px-1 py-1.5 text-sm text-zinc-950 outline-none placeholder:text-zinc-500 disabled:text-zinc-400 dark:text-zinc-50 dark:placeholder:text-zinc-400 overflow-y-auto custom-textarea-scrollbar"
              disabled={isStreaming || isUploading}
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={handleKeyDown}
              onCompositionStart={() => (isComposingRef.current = true)}
              onCompositionEnd={() => {
                // 使用 setTimeout 是为了让 handleKeyDown 能在合成结束的那一刻依然看到合成状态，
                // 避免某些浏览器下 compositionEnd 先于 keydown 触发导致的回车误发。
                setTimeout(() => {
                  isComposingRef.current = false;
                }, 0);
              }}
              onPaste={handlePaste}
              placeholder="输入方向、题目或粘贴 JD..."
              value={value}
              rows={1}
              suppressHydrationWarning
            />

            {/* 发送消息按钮与微动效 Tooltip */}
            <div className="flex items-center justify-center shrink-0 mb-[2px]">
              <Button
                aria-label="发送"
                className={cn(
                  "size-8 rounded-xl transition-all",
                  (value.trim() || attachments.length > 0)
                    ? "bg-[#534AB7] text-white hover:bg-[#463fa1]"
                    : "bg-zinc-100 text-zinc-400 hover:bg-zinc-100 dark:bg-zinc-800",
                )}
                disabled={(!value.trim() && attachments.length === 0) || isStreaming || isUploading}
                size="icon"
                type="submit"
                onMouseEnter={(e) => {
                  if ((value.trim() || attachments.length > 0) && !isStreaming && !isUploading) {
                    showTooltip("发送消息", e);
                  }
                }}
                onMouseLeave={hideTooltip}
              >
                <Send className="size-4" />
              </Button>
            </div>
          </div>
        </div>
      </form>

      {/* 【NEW】万能高保真文件预览大浮层 - 完美集成图片全屏、PDF 在线 iframe 阅读、Word等Office大名片及本地下载 */}
      {previewAttachment && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm transition-all duration-300 animate-in fade-in"
          onClick={() => setPreviewAttachment(null)}
        >
          {/* 统一顶栏关闭按钮 */}
          <button
            type="button"
            aria-label="关闭预览"
            onClick={() => setPreviewAttachment(null)}
            className="absolute top-5 right-5 z-55 size-10 bg-white/10 hover:bg-white/20 text-white rounded-full flex items-center justify-center backdrop-blur-md transition-all active:scale-95 cursor-pointer border border-white/10 hover:rotate-90 duration-300"
          >
            <X className="size-6" />
          </button>

          {previewAttachment.type.startsWith("image/") || 
           /\.(jpg|jpeg|png|gif|webp|bmp|ico|svg)$/i.test(previewAttachment.name) ? (
            // 1. 图片全屏放大预览模式
            <img
              src={previewAttachment.url}
              alt="图片预览"
              className="max-h-[85vh] max-w-[90vw] rounded-2xl object-contain shadow-2xl animate-in zoom-in-95 duration-200 cursor-default"
              onClick={(e) => e.stopPropagation()}
            />
          ) : previewAttachment.type === "application/pdf" || previewAttachment.name.endsWith(".pdf") ? (
            // 2. PDF 内置 iframe 直接在线阅读模式
            <div 
              className="w-[85vw] h-[85vh] max-w-5xl bg-white dark:bg-zinc-900 rounded-2xl overflow-hidden relative border border-zinc-200 dark:border-zinc-800 shadow-2xl flex flex-col animate-in zoom-in-95 duration-250"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex h-12 shrink-0 items-center justify-between border-b border-zinc-100 bg-zinc-50/80 px-5 dark:border-zinc-800 dark:bg-zinc-900/80">
                <span className="truncate text-xs font-semibold text-zinc-800 dark:text-zinc-200 max-w-[70%]">
                  正在预览: {previewAttachment.name}
                </span>
                <span className="text-[10px] text-zinc-400 font-medium">
                  PDF 阅读器 ({formatBytes(previewAttachment.size)})
                </span>
              </div>
              <iframe
                src={previewAttachment.url}
                className="w-full flex-1 border-none bg-zinc-100 dark:bg-zinc-950"
                title={previewAttachment.name}
              />
            </div>
          ) : (
            // 3. Word文档及其他二进制文件的精美信息名片大卡片 + 本地下载与查看按钮
            <div 
              className="w-[420px] bg-white dark:bg-zinc-900 rounded-3xl border border-zinc-150 dark:border-zinc-800 p-8 flex flex-col items-center text-center shadow-2xl animate-in zoom-in-95 duration-250"
              onClick={(e) => e.stopPropagation()}
            >
              {/* 大图标 */}
              <div className={cn("flex size-20 items-center justify-center rounded-2xl text-white shadow-lg mb-5", getFileConfig(previewAttachment.name, previewAttachment.type).bgColor)}>
                <FileText className="size-10" />
              </div>

              {/* 文件名与大小 */}
              <h2 className="text-base font-bold text-zinc-800 dark:text-zinc-100 px-2 line-clamp-2 select-text">
                {previewAttachment.name}
              </h2>
              <span className="text-xs font-semibold text-zinc-400 mt-1 select-none">
                {getFileConfig(previewAttachment.name, previewAttachment.type).label} · {formatBytes(previewAttachment.size)}
              </span>

              {/* 贴心说明 */}
              <p className="text-xs text-zinc-400/80 dark:text-zinc-500 mt-4 max-w-[280px] leading-relaxed select-none">
                由于浏览器原生安全限制，该类型文件无法直接在线直接渲染。已为您提供下载与本地查看。
              </p>

              {/* 炫酷的下载按钮 */}
              <a
                href={previewAttachment.url}
                download={previewAttachment.name}
                className="mt-8 flex w-full h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#534AB7] to-[#4339b0] text-white hover:from-[#4339b0] hover:to-[#382da3] font-semibold text-xs shadow-md shadow-indigo-500/10 hover:shadow-indigo-500/20 active:scale-95 transition-all"
              >
                <Download className="size-4 animate-bounce" />
                下载并本地查看
              </a>
            </div>
          )}
        </div>
      )}

      {/* 【NEW】全局 Fixed 漂浮式高质感黑色 Tooltip 渲染，实现与输入框容器完全脱离，自由遮盖一切层级 */}
      {globalTooltip.visible && (
        <div
          style={{
            position: "fixed",
            left: `${globalTooltip.x}px`,
            top: `${globalTooltip.y}px`,
            transform: "translate(-50%, -100%)",
          }}
          className="pointer-events-none z-50 rounded-lg bg-zinc-950 px-2.5 py-1.5 text-[11px] font-semibold text-white shadow-xl dark:bg-zinc-50 dark:text-zinc-950 whitespace-nowrap animate-in fade-in-0 zoom-in-95 duration-100 shadow-black/25 flex items-center justify-center"
        >
          {globalTooltip.text}
        </div>
      )}
    </>
  );
}
