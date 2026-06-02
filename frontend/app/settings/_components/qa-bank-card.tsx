"use client";

import React, { useRef, useState } from "react";
import { Download, Upload, ClipboardList, Briefcase, UserCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  downloadQABankTemplate,
  fetchQABankSummary,
  uploadQABank,
  type QABankSummary,
} from "@/lib/qa-bank";
import { cn } from "@/lib/utils";

type Props = {
  token: string;
  initialSummary: QABankSummary;
};

type Category = "hr" | "project" | "technical";

export function QABankCard({ token, initialSummary }: Props) {
  const [summary, setSummary] = useState<QABankSummary>(initialSummary);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Category>("hr");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const tabs: { id: Category; label: string; icon: React.ReactNode }[] = [
    { id: "hr", label: "HR 题目", icon: <UserCircle className="size-4" /> },
    { id: "project", label: "项目经验", icon: <Briefcase className="size-4" /> },
    { id: "technical", label: "技术题目", icon: <ClipboardList className="size-4" /> },
  ];

  const handleDownload = async () => {
    try {
      await downloadQABankTemplate({ token, category: activeTab });
    } catch {
      setUploadMsg("下载失败，请稍后重试");
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    setIsUploading(true);
    setUploadMsg(null);
    try {
      const result = await uploadQABank({ token, file });
      const total = Object.values(result.imported).reduce((a, b) => (a || 0) + (b || 0), 0);
      const skipText = result.skipped > 0 ? `，跳过 ${result.skipped} 条` : "";
      setUploadMsg(`上传成功，导入 ${total} 条题目${skipText}`);
      const newSummary = await fetchQABankSummary({ token });
      setSummary(newSummary);
    } catch (err) {
      setUploadMsg(err instanceof Error ? err.message : "上传失败");
    } finally {
      setIsUploading(false);
    }
  };

  const getCount = (cat: Category) => {
    if (cat === "hr") return summary.hr;
    if (cat === "project") return summary.project;
    if (cat === "technical") return summary.technical;
    return 0;
  };

  return (
    <Card className="p-6 border-[#e8e7e2] bg-white shadow-sm overflow-hidden">
      <div className="mb-6">
        <h3 className="font-bold text-[#171717] text-base mb-1">面试题库</h3>
        <p className="text-xs text-[#8a8a8a]">按分类准备题目，让 AI Coach 针对性地考你</p>
      </div>

      {/* Tab Header */}
      <div className="flex border-b border-[#e8e7e2] mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id);
              setUploadMsg(null);
            }}
            className={cn(
              "flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors relative",
              activeTab === tab.id
                ? "text-[#4f46e5]"
                : "text-[#8a8a8a] hover:text-[#525252]"
            )}
          >
            {tab.icon}
            {tab.label}
            <span className="ml-1 text-[10px] bg-[#f5f3ff] text-[#4f46e5] px-1.5 py-0.5 rounded-full border border-[#4f46e5]/10">
              {getCount(tab.id)}
            </span>
            {activeTab === tab.id && (
              <div className="absolute bottom-0 left-0 w-full h-0.5 bg-[#4f46e5]" />
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-[#fafafa] border border-[#f0f0f0]">
          <div>
            <p className="text-sm font-semibold text-[#171717]">
              {tabs.find((t) => t.id === activeTab)?.label} 管理
            </p>
            <p className="text-xs text-[#8a8a8a] mt-1">
              当前分类已收录 {getCount(activeTab)} 条题目。支持 Markdown 格式上传。
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              className="gap-1.5 text-xs rounded-lg border-[#e8e7e2] text-[#525252] h-9"
            >
              <Download className="size-3.5" /> 下载模板
            </Button>
            <Button
              size="sm"
              onClick={handleUploadClick}
              disabled={isUploading}
              className="bg-[#4f46e5] hover:bg-[#4338ca] text-white gap-1.5 text-xs rounded-lg h-9 shadow-sm"
            >
              <Upload className="size-3.5" />
              {isUploading ? "上传中..." : "上传题库"}
            </Button>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".md"
              className="hidden"
            />
          </div>
        </div>

        {uploadMsg && (
          <div className={cn(
            "text-xs p-3 rounded-lg border",
            uploadMsg.includes("失败") 
              ? "bg-red-50 text-red-600 border-red-100" 
              : "bg-emerald-50 text-emerald-600 border-emerald-100"
          )}>
            {uploadMsg}
          </div>
        )}
      </div>

      <div className="mt-6 pt-4 border-t border-[#f0f0f0]">
        <p className="text-[10px] text-[#a1a1a1] leading-relaxed italic">
          * 提示：你可以一次性在一个 Markdown 文件中包含多个分类（使用 ## 技术题 等标题），
          上传后系统会自动按分类更新。
        </p>
      </div>
    </Card>
  );
}
