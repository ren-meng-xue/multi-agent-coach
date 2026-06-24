---
description: 浏览 YouTube 频道视频分类，按分类查看详细列表，可对接字幕提取
argument-hint: "<channel_url>"
---

# youtube-channel-browser

给定 YouTube 频道 URL，完成以下工作流：

1. 获取频道全部视频列表
2. 按主题分类，输出分类总览
3. 用户指定分类后，输出该分类的详细表格（中文标题 + 时长 + URL）
4. 可衔接 `/video-to-chinese` 或字幕提取脚本

---

## 第一步：获取视频列表

```bash
python scripts/youtube-transcripts.py <channel_url> --list 2>/dev/null \
  | head -5
```

同时用以下命令拿到结构化数据供后续分类：

```bash
yt-dlp --flat-playlist --dump-json --no-warnings "<channel_url>/videos" \
  | python3 -c "
import json, sys
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        v = json.loads(line)
        print(v.get('playlist_index',0), '|', v.get('title',''), '|', v.get('duration_string','?'), '|', 'https://www.youtube.com/watch?v=' + v.get('id',''))
    except: pass
"
```

---

## 第二步：分析标题，按主题分类

拿到视频列表后，分析所有标题，将视频归入若干主题分类。

**分类规则：**

- 根据标题关键词归类（如 Codex、n8n、Agent、RAG、LinkedIn、内容创作、SaaS、MCP 等）
- 分类名称使用中文
- 每个分类显示视频数量
- 无法归类的统一放入「其他」

**输出格式（分类总览）：**

```
共 X 个视频，分为 N 类：

A. 分类名称（X 个）
B. 分类名称（X 个）
C. 分类名称（X 个）
...

输入分类字母（如 A）或分类名称，查看该分类的详细列表。
```

---

## 第三步：用户指定分类 → 输出详细表格

用户输入分类字母或名称后，输出该分类的完整表格：

**输出格式：**

```
## 分类名称（X 个）

| # | 标题（中文） | 时长 | URL |
|---|------------|------|-----|
| 56 | n8n 的新 AI 秒速构建工作流 | 17:11 | https://... |
| 61 | 复制这个广告自动化策略 | 36:15 | https://... |
...

如需提取某个视频的完整字幕并生成中文笔记，可使用 /video-to-chinese <URL>
```

**标题翻译规则：**

- 全部翻译成简体中文
- 技术术语保留英文原词（n8n、Codex、MCP、RAG、API、SaaS 等）
- 翻译要准确传达原标题意图，不要字面直译

---

## 第四步（可选）：衔接字幕提取

用户确认要提取某分类后，给出提取命令：

```bash
python scripts/youtube-transcripts.py <channel_url> --select <编号列表>
```

编号来自第二步的视频列表序号（playlist_index）。

---

## 注意事项

- 视频列表以频道当前实际内容为准，每次调用重新获取
- 分类是基于标题的主观判断，同一视频可能跨多个主题，归入最相关的分类
- 字幕提取需要 Chrome 浏览器已登录 YouTube
