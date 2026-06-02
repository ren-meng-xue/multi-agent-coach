---
description: 视频字幕转中文 markdown。规则待补完。
argument-hint: "<operation>"
disable-model-invocation: true
---

# video-to-chinese

skill 注册入口。原完整规则文件已下线，待补完触发方式、写入边界、二次确认和删除规则。

配套 hook 仍在运行：

- `.claude/hooks/video_to_chinese_pre_write.py`（PreToolUse / Write）
- `.claude/hooks/video_to_chinese_post_write.py`（PostToolUse / Write）

历史产出位于 `.claude/skills/video-to-chinese/docs/`。
