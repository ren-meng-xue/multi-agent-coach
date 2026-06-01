"use client";
import React, { useRef, useState } from "react";
import { Card } from "@/components/ui/card";
import { uploadResume, type UserProfile } from "@/lib/user";
import { cn } from "@/lib/utils";
import { 
  FileText, 
  Upload, 
  Loader2, 
  Paperclip, 
  CheckCircle2, 
  BookOpen 
} from "lucide-react";

type Props = {
  token: string;
  profile: UserProfile;
  onUpdate: (profile: UserProfile) => void;
};

export function ResumeCard({ token, profile, onUpdate }: Props) {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const processFile = async (file: File) => {
    if (file.size > 5 * 1024 * 1024) {
      setError("文件大小超出限制：最大支持 5MB");
      return;
    }

    setIsUploading(true);
    setError(null);
    try {
      const updatedProfile = await uploadResume({ token, file });
      onUpdate(updatedProfile);
    } catch (err) {
      setError(err instanceof Error ? err.message : "简历解析与分析队列异常，请重试");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  return (
    <Card className="rounded-[var(--mac-radius)] border border-[var(--mac-border-light)] bg-white p-6 shadow-[var(--mac-shadow-xs)] flex flex-col max-h-full transition-all duration-300">
      {/* 标题区 - 纯文字，无英文，嵌入精致细线图标，高度与左侧头像完美物理对齐 */}
      <div className="pb-4 border-b border-[var(--mac-border-light)] shrink-0">
        <h3 className="text-lg font-normal text-[var(--mac-text-primary)] font-serif tracking-tight flex items-center gap-2 h-10">
          <FileText className="size-4.5 text-[var(--mac-text-secondary)] shrink-0" />
          <span>个人简历</span>
        </h3>
      </div>

      {/* 动态区域 */}
      <div className="flex-1 min-h-0 flex flex-col justify-start mt-4">
        {/* 说明导语移至线下 */}
        <p className="text-xs text-[var(--mac-text-tertiary)] leading-relaxed font-sans mb-4 shrink-0">
          上传并绑定您的最新简历。AI Coach 将围绕您的真实项目背景，深度定制模拟实战演练方案。
        </p>

        {!profile.resume_filename ? (
          /* 未上传简历：嵌入精致的 Upload/Loader 图标，大幅收缩垂直高度，解析时加入呼吸动态 */
          <div 
            onClick={handleUploadClick}
            className={cn(
              "border border-dashed border-[#3b82f6]/40 bg-[#f0f7ff]/70 rounded-[var(--mac-radius-sm)] flex flex-col items-center justify-center h-36 px-4 cursor-pointer transition-all duration-300 hover:bg-white hover:border-[#3b82f6] hover:shadow-[0_0_0_1px_rgba(59,130,246,0.1),var(--mac-shadow-xs)] group shrink-0",
              isUploading && "pointer-events-none opacity-50 bg-white border-[#3b82f6] animate-pulse"
            )}
          >
            <div className="text-center space-y-2 z-10">
              <div className="flex items-center justify-center">
                {isUploading ? (
                  <Loader2 className="size-4 text-[var(--mac-text-secondary)] animate-spin" />
                ) : (
                  <Upload className="size-4 text-[#3b82f6] group-hover:text-[#2563eb] transition-colors" />
                )}
              </div>
              <div className="space-y-1">
                <p className="text-sm text-[var(--mac-text-primary)] font-medium font-sans">
                  {isUploading ? "正在解析并载入简历数据..." : "点击或拖拽上传个人简历"}
                </p>
                <p className="text-[11px] text-[var(--mac-text-tertiary)] max-w-[320px] leading-relaxed font-sans mx-auto">
                  {isUploading ? "解析可能需要几秒钟，请稍候" : "支持 PDF / TXT / MD 格式，大小限制 5MB"}
                </p>
              </div>
            </div>
          </div>
        ) : (
          /* 已上传简历：与大列表风格统一的紧凑行式展示，更新时加入呼吸动态，嵌入 Paperclip 图标 */
          <div className="space-y-4 animate-in fade-in duration-300 flex-1 min-h-0 flex flex-col">
            {/* 简历文件信息行 - 样式呼应基本档案，解析时整行渐进呼吸 */}
            <div className={cn(
              "border border-[var(--mac-border-light)] bg-[#fafaf8] p-4 rounded-[var(--mac-radius-sm)] flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xs hover:bg-white hover:border-[var(--mac-border)] transition-all duration-200 shrink-0",
              isUploading && "pointer-events-none opacity-60 bg-white border-[var(--mac-border)] animate-pulse"
            )}>
              <div className="flex items-start gap-3 min-w-0">
                <Paperclip className="size-4 text-[var(--mac-text-tertiary)] mt-1 shrink-0" />
                <div className="min-w-0">
                  <span className="text-xs text-[var(--mac-text-tertiary)] block mb-0.5">
                    {isUploading ? "正在解析新简历" : "已绑定简历"}
                  </span>
                  <h4 className="text-sm font-medium text-[var(--mac-text-primary)] truncate max-w-[260px] md:max-w-[400px] font-sans">
                    {profile.resume_filename}
                  </h4>
                  <p className={cn(
                    "text-[11px] font-sans mt-1.5 flex items-center gap-1.5",
                    isUploading ? "text-[var(--mac-text-tertiary)]" : "text-[var(--mac-accent-emerald)] font-medium"
                  )}>
                    {isUploading ? (
                      "正在读取简历数据，请稍候..."
                    ) : (
                      <>
                        <CheckCircle2 className="size-3.5 text-[var(--mac-accent-emerald)] shrink-0" />
                        <span>已成功绑定演练上下文</span>
                      </>
                    )}
                  </p>
                </div>
              </div>
              
              <button
                onClick={handleUploadClick}
                disabled={isUploading}
                className={cn(
                  "text-xs text-[var(--mac-text-secondary)] hover:text-[var(--mac-text-primary)] font-medium cursor-pointer border border-[var(--mac-border-light)] px-3.5 py-2 rounded-[var(--mac-radius-xs)] hover:bg-[#fafaf8] bg-white shadow-xs active:scale-[0.98] transition-all font-sans self-start sm:self-auto flex items-center gap-1.5",
                  isUploading && "opacity-50 pointer-events-none"
                )}
              >
                {isUploading ? (
                  <>
                    <Loader2 className="size-3 animate-spin shrink-0" />
                    <span>更新中...</span>
                  </>
                ) : (
                  <>
                    <Upload className="size-3 text-[var(--mac-text-secondary)] shrink-0" />
                    <span>更新简历</span>
                  </>
                )}
              </button>
            </div>

            {/* AI Coach 简历诊断建议 */}
            {profile.evaluation && !isUploading && (
              <div className="space-y-2 flex flex-col min-h-0 shrink-0">
                <span className="text-xs font-semibold tracking-wider text-[var(--mac-text-secondary)] font-sans uppercase flex items-center gap-2 shrink-0">
                  <BookOpen className="size-3.5 text-[var(--mac-text-tertiary)] shrink-0" />
                  <span>简历洞察与诊断建议</span>
                </span>
                <div className="p-4 bg-[#fafaf8] border border-[var(--mac-border-light)] rounded-[var(--mac-radius-sm)] overflow-y-auto max-h-[calc(100vh-310px)] shrink-0">
                  <div className="text-xs text-[var(--mac-text-secondary)] leading-relaxed space-y-2 whitespace-pre-wrap font-sans">
                    {profile.evaluation}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 错误提示 */}
        {error && (
          <div className="mt-3 p-3 border border-rose-100 bg-rose-50/30 text-rose-600 text-xs rounded-[var(--mac-radius-xs)] flex items-center gap-2 font-sans">
            <span>无法上传文件: {error}</span>
          </div>
        )}
      </div>

      {/* 隐藏的 input 上传节点 */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".pdf,.txt,.md"
        className="hidden"
      />
    </Card>
  );
}

