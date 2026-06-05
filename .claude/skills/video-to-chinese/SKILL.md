---
description: 把 YouTube 视频转成中文 Markdown 笔记，输出字幕原文+提炼总结两份文档。
argument-hint: "<YouTube URL>"
---

# video-to-chinese

给定 YouTube URL，产出两份文档存入 `docs/`：

1. **字幕原文**（`-transcript.md`）：作者说的每一句话，逐段保留，不压缩
2. **提炼总结**（`.md`）：结构化中文笔记，含必填章节

---

## 第一步：下载字幕

```bash
yt-dlp --cookies-from-browser chrome \
  --write-subs --write-auto-subs \
  --sub-langs "zh,zh-Hans,zh-Hant,zh-CN,zh-TW,en" \
  --sub-format "vtt/best" \
  --skip-download \
  -o "/tmp/video-%(id)s" \
  "<URL>"
```

**字幕轨道优先级（按顺序尝试）：**

1. `zh` / `zh-Hans` / `zh-CN`（中文原声视频首选）
2. `zh-Hant` / `zh-TW`
3. `en`（英文原声视频首选）
4. `en-zh`（自动翻译，最后兜底）

**选轨规则：**

- 先判断视频语言（看标题/描述语言）
- 优先使用与**原声语言一致**的字幕轨道
- 禁止直接使用"原声→翻译"轨道（如中文视频用 en-zh）—— 会引入双重翻译失真
- 若只有翻译轨，在来源与限制章节中说明

**提取字幕为带时间戳的纯文本：**

```python
import re

with open('/tmp/video-<ID>.<lang>.vtt', 'r') as f:
    content = f.read()

lines = content.split('\n')
segments = []
i = 0
while i < len(lines):
    line = lines[i].strip()
    if '-->' in line:
        time_match = re.match(r'(\d{2}:\d{2}:\d{2})', line)
        if time_match:
            ts = time_match.group(1)
            texts = []
            i += 1
            while i < len(lines) and lines[i].strip() and '-->' not in lines[i]:
                text = re.sub(r'<[^>]+>', '', lines[i].strip())
                if text:
                    texts.append(text)
                i += 1
            if texts:
                segments.append((ts, ' '.join(texts)))
    else:
        i += 1

# 去除相邻重复
deduped = []
prev = ''
for ts, text in segments:
    if text != prev:
        deduped.append((ts, text))
        prev = text
```

---

## 第二步：写字幕原文文件

文件名格式：`YYYY-MM-DD-<slug>-transcript.md`

**格式要求：**

- 保留作者说的**每一句话**，不得删减、压缩或改写
- 将连续的短碎片（同一语义单元内）拼接成完整句子/段落
- 每隔 60–90 秒或话题切换处加一行时间戳标记 `**[HH:MM:SS]**`
- 输出语言与字幕原文一致（中文视频输出中文，英文视频输出英文）

**文件头格式：**

```markdown
# 原始字幕：<视频标题>

来源：<URL>
作者：<频道名>
字幕轨道：<使用的轨道，如 zh / en>
```

---

## 第三步：写提炼总结文件

文件名格式：`YYYY-MM-DD-<slug>.md`

**必填章节（hook 会校验）：**

- `## 一句话总结`
- `## 核心观点`
- `## 来源与限制`

**推荐章节：**

- `## 时间线笔记` — 表格格式，时间点 + 内容摘要
- `## 可执行建议`
- `## 关键术语`
- `## 适合谁看`

**写作规范：**

- 全部使用简体中文（无论原视频语言）
- 核心观点用编号列表，每条加粗标题 + 说明
- 时间线表格：`| 时间点 | 内容 |`

---

## 文件命名 slug 规则

- 全小写，单词用连字符
- 反映视频核心主题，不超过 6 个单词
- 示例：`codex-10-best-practices`、`claude-code-15-things`

---

## 配套 hook

- `.claude/hooks/video_to_chinese_pre_write.py`：Write 前校验文件名格式和必填章节
- `.claude/hooks/video_to_chinese_post_write.py`：Write 后打印存档确认

历史产出位于 `.claude/skills/video-to-chinese/docs/`。
