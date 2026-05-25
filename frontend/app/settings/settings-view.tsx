"use client";

import React, { useState, useEffect } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  fetchUserProfile,
  updateUserProfile,
  fetchUserStories,
  createUserStory,
  updateUserStory,
  deleteUserStory,
  type UserProfile,
  type UserStory,
} from "@/lib/user";
import { Plus, Pencil, Trash2, Save, X, Sparkles } from "lucide-react";

export function SettingsView() {
  const { isLoaded: authLoaded, isSignedIn, getToken } = useAuth();
  const { user: clerkUser } = useUser();
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [stories, setStories] = useState<UserStory[]>([]);
  
  // 编辑状态
  const [editingProfile, setEditingProfile] = useState(false);
  const [targetRole, setTargetRole] = useState("");
  const [workYears, setWorkYears] = useState("");
  
  // 故事编辑状态
  const [isStoryModalOpen, setIsStoryModalOpen] = useState(false);
  const [currentStory, setCurrentStory] = useState<Partial<UserStory> | null>(null);

  useEffect(() => {
    if (!authLoaded || !isSignedIn) return;

    const loadData = async () => {
      try {
        const token = await getToken();
        if (!token) return;

        const [userProfile, userStories] = await Promise.all([
          fetchUserProfile({ token }),
          fetchUserStories({ token }),
        ]);

        setProfile(userProfile);
        setStories(userStories);
        setTargetRole(userProfile.target_role || "");
        setWorkYears(userProfile.work_years || "");
      } catch (error) {
        console.error("Failed to load settings:", error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [authLoaded, isSignedIn, getToken]);

  const handleSaveProfile = async () => {
    try {
      const token = await getToken();
      if (!token) return;

      const updated = await updateUserProfile({
        token,
        profile: { target_role: targetRole, work_years: workYears },
      });

      setProfile(updated);
      setEditingProfile(false);
    } catch (error) {
      console.error("Failed to update profile:", error);
    }
  };

  const handleOpenStoryModal = (story?: UserStory) => {
    if (story) {
      setCurrentStory(story);
    } else {
      setCurrentStory({
        title: "",
        role: "",
        tags: [],
        content_json: { situation: "", task: "", action: "", result: "" },
      });
    }
    setIsStoryModalOpen(true);
  };

  const handleSaveStory = async () => {
    if (!currentStory || !currentStory.title) return;

    try {
      const token = await getToken();
      if (!token) return;

      if (currentStory.id) {
        const updated = await updateUserStory({
          token,
          storyId: currentStory.id,
          story: {
            title: currentStory.title,
            role: currentStory.role,
            tags: currentStory.tags,
            content_json: currentStory.content_json,
          },
        });
        setStories(stories.map((s) => (s.id === updated.id ? updated : s)));
      } else {
        const created = await createUserStory({
          token,
          story: {
            title: currentStory.title!,
            role: currentStory.role || null,
            tags: currentStory.tags || null,
            content_json: currentStory.content_json!,
          },
        });
        setStories([created, ...stories]);
      }
      setIsStoryModalOpen(false);
    } catch (error) {
      console.error("Failed to save story:", error);
    }
  };

  const handleDeleteStory = async (id: string) => {
    if (!confirm("确定要删除这个故事吗？")) return;
    try {
      const token = await getToken();
      if (!token) return;
      await deleteUserStory({ token, storyId: id });
      setStories(stories.filter((s) => s.id !== id));
    } catch (error) {
      console.error("Failed to delete story:", error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#4f46e5]"></div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-6xl mx-auto py-8 px-4 md:px-6">
      <div className="flex flex-col md:flex-row gap-8">
        
        {/* 左侧：个人资料 */}
        <div className="w-full md:w-1/3 space-y-6">
          <Card className="p-6 border-[#e8e7e2] bg-white shadow-sm overflow-hidden relative">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#4f46e5] to-[#7c3aed]" />
            
            <div className="flex items-center gap-4 mb-8">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-[#4f46e5] to-[#7c3aed] flex items-center justify-center text-white text-2xl font-bold shadow-lg overflow-hidden">
                {clerkUser?.imageUrl ? (
                  <img src={clerkUser.imageUrl} alt="Avatar" className="w-full h-full object-cover" />
                ) : (
                  clerkUser?.firstName?.charAt(0) || "U"
                )}
              </div>
              <div>
                <h2 className="font-[var(--mac-font-display)] text-2xl text-[#171717]">
                  {clerkUser?.fullName || "面试者"}
                </h2>
                <p className="text-sm text-[#8a8a8a]">{clerkUser?.primaryEmailAddress?.emailAddress}</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-[10px] font-extrabold uppercase tracking-widest text-[#8a8a8a]">目标岗位</Label>
                {editingProfile ? (
                  <Input 
                    value={targetRole} 
                    onChange={(e) => setTargetRole(e.target.value)}
                    className="bg-[#fafaf8] border-[#e8e7e2] focus:ring-[#4f46e5]/20 focus:border-[#4f46e5]"
                    placeholder="例如：AI Agent 工程师"
                  />
                ) : (
                  <p className="text-[#171717] font-medium">{profile?.target_role || "未设置"}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label className="text-[10px] font-extrabold uppercase tracking-widest text-[#8a8a8a]">工作年限</Label>
                {editingProfile ? (
                  <Input 
                    value={workYears} 
                    onChange={(e) => setWorkYears(e.target.value)}
                    className="bg-[#fafaf8] border-[#e8e7e2] focus:ring-[#4f46e5]/20 focus:border-[#4f46e5]"
                    placeholder="例如：3 年"
                  />
                ) : (
                  <p className="text-[#171717] font-medium">{profile?.work_years || "未设置"}</p>
                )}
              </div>

              <div className="pt-4">
                {editingProfile ? (
                  <div className="flex gap-2">
                    <Button onClick={handleSaveProfile} className="flex-1 bg-[#171717] hover:bg-black text-white">
                      保存
                    </Button>
                    <Button variant="outline" onClick={() => setEditingProfile(false)} className="flex-1 border-[#e8e7e2]">
                      取消
                    </Button>
                  </div>
                ) : (
                  <Button 
                    variant="outline" 
                    onClick={() => setEditingProfile(true)} 
                    className="w-full border-[#e8e7e2] hover:bg-[#fafaf8] text-[#525252]"
                  >
                    修改资料
                  </Button>
                )}
              </div>
            </div>
          </Card>

          <Card className="p-6 border-[#e8e7e2] bg-[#f5f3ff] shadow-sm">
            <h3 className="text-sm font-bold text-[#4f46e5] mb-2 flex items-center gap-2">
              <Sparkles className="size-4" /> AI 教练提醒
            </h3>
            <p className="text-xs text-[#525252] leading-relaxed">
              Coach 会根据你在这里设置的<b>目标岗位</b>来调整面试题库的难度。同时，<b>故事库</b>里的内容会被 AI 提取，作为追问的背景素材，记得保持更新。
            </p>
          </Card>
        </div>

        {/* 右侧：故事库 */}
        <div className="flex-1 space-y-6">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h2 className="font-[var(--mac-font-display)] text-2xl text-[#171717]">STAR 故事库</h2>
              <p className="text-sm text-[#8a8a8a]">存储你的项目精华，AI 会在面试中引用它们</p>
            </div>
            <Button onClick={() => handleOpenStoryModal()} className="bg-[#4f46e5] hover:bg-[#4338ca] text-white gap-2 rounded-xl">
              <Plus className="size-4" /> 添加故事
            </Button>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {stories.length === 0 ? (
              <div className="text-center py-20 border-2 border-dashed border-[#e8e7e2] rounded-2xl bg-white">
                <p className="text-[#8a8a8a]">还没有故事？点击右上方按钮开始第一个 STAR 故事吧。</p>
              </div>
            ) : (
              stories.map((story) => (
                <Card key={story.id} className="p-5 border-[#e8e7e2] bg-white hover:shadow-md transition-shadow group relative">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h3 className="font-bold text-[#171717] text-lg">{story.title}</h3>
                      <p className="text-xs text-[#4f46e5] font-medium mt-0.5">{story.role}</p>
                    </div>
                    <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button variant="ghost" size="icon" onClick={() => handleOpenStoryModal(story)} className="size-8 text-[#8a8a8a] hover:text-[#4f46e5]">
                        <Pencil className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDeleteStory(story.id)} className="size-8 text-[#8a8a8a] hover:text-[#e11d48]">
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>
                  <p className="text-sm text-[#525252] line-clamp-2 leading-relaxed mb-4">
                    {story.content_json.situation}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {story.tags?.map((tag) => (
                      <span key={tag} className="px-2.5 py-1 bg-[#f5f3ff] text-[#4f46e5] text-[10px] font-bold rounded-lg border border-[#4f46e5]/10">
                        {tag}
                      </span>
                    ))}
                  </div>
                </Card>
              ))
            )}
          </div>
        </div>
      </div>

      {/* 故事编辑模态框 */}
      {isStoryModalOpen && currentStory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <Card className="w-full max-w-2xl bg-white shadow-2xl rounded-2xl overflow-hidden max-h-[90vh] flex flex-col">
            <div className="p-6 border-b border-[#e8e7e2] flex items-center justify-between shrink-0">
              <h3 className="font-[var(--mac-font-display)] text-2xl text-[#171717]">
                {currentStory.id ? "编辑 STAR 故事" : "添加新故事"}
              </h3>
              <Button variant="ghost" size="icon" onClick={() => setIsStoryModalOpen(false)}>
                <X className="size-5" />
              </Button>
            </div>
            
            <div className="p-6 overflow-y-auto space-y-5">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>项目名称</Label>
                  <Input 
                    value={currentStory.title} 
                    onChange={(e) => setCurrentStory({...currentStory, title: e.target.value})}
                    placeholder="如：LangGraph 多 Agent 系统"
                  />
                </div>
                <div className="space-y-2">
                  <Label>担任角色</Label>
                  <Input 
                    value={currentStory.role || ""} 
                    onChange={(e) => setCurrentStory({...currentStory, role: e.target.value})}
                    placeholder="如：核心开发者 / 架构师"
                  />
                </div>
              </div>

              <div className="space-y-4 pt-2">
                <div className="space-y-2">
                  <Label className="text-[#4f46e5] font-bold">Situation (情境)</Label>
                  <Textarea 
                    value={currentStory.content_json?.situation || ""} 
                    onChange={(e) => setCurrentStory({
                      ...currentStory, 
                      content_json: { ...currentStory.content_json, situation: e.target.value }
                    })}
                    placeholder="发生了什么？当时面临什么挑战？"
                    rows={2}
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#4f46e5] font-bold">Task (任务)</Label>
                  <Textarea 
                    value={currentStory.content_json?.task || ""} 
                    onChange={(e) => setCurrentStory({
                      ...currentStory, 
                      content_json: { ...currentStory.content_json, task: e.target.value }
                    })}
                    placeholder="你的目标是什么？需要解决什么具体问题？"
                    rows={2}
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#4f46e5] font-bold">Action (行动)</Label>
                  <Textarea 
                    value={currentStory.content_json?.action || ""} 
                    onChange={(e) => setCurrentStory({
                      ...currentStory, 
                      content_json: { ...currentStory.content_json, action: e.target.value }
                    })}
                    placeholder="你具体是怎么做的？运用了什么技术？"
                    rows={4}
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#4f46e5] font-bold">Result (结果)</Label>
                  <Textarea 
                    value={currentStory.content_json?.result || ""} 
                    onChange={(e) => setCurrentStory({
                      ...currentStory, 
                      content_json: { ...currentStory.content_json, result: e.target.value }
                    })}
                    placeholder="最终取得了什么成果？（请尽量量化，如提升 30% 性能）"
                    rows={2}
                  />
                </div>
              </div>
            </div>

            <div className="p-6 border-t border-[#e8e7e2] bg-[#fafaf8] flex justify-end gap-3 shrink-0">
              <Button variant="outline" onClick={() => setIsStoryModalOpen(false)}>取消</Button>
              <Button onClick={handleSaveStory} className="bg-[#4f46e5] hover:bg-[#4338ca] text-white px-8">
                保存故事
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
