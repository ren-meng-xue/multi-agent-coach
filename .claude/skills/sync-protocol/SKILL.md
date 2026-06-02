---
description: Project skill entry. Full rules live in .ai/skills/sync-protocol.md.
argument-hint: "<audit|sync|propose|apply --confirmed|orphans|stale|update-index>"
disable-model-invocation: true
---

# sync-protocol

本文件只是 Claude Code 的 skill 注册入口。

完整规则以项目协议文件为唯一来源：

```text
.ai/skills/sync-protocol.md
```

执行前必须先读取该文件，并遵守其中的触发方式、写入边界、二次确认和删除规则。
