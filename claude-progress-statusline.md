# Claude Code 自定义 Progress StatusLine

## 背景

Claude Code 的 `statusLine` 本质上是执行一个命令，然后将命令输出显示在底部状态栏。

例如当前配置：

```json
{
  "statusLine": {
    "type": "command",
    "command": "ccstatusline",
    "padding": 0,
    "refreshInterval": 10
  }
}
```

实际上就是每隔 10 秒执行一次：

```bash
ccstatusline
```

然后把输出渲染到底部。

因此我们完全可以替换成自己的脚本，实现类似 GSD / Agentic-OS 的进度条效果。

---

# 创建 Progress StatusLine

## 1. 创建脚本目录

```bash
mkdir -p ~/.claude/scripts
```

---

## 2. 创建状态栏脚本

```bash
nano ~/.claude/scripts/statusline-progress.sh
```

写入：

```bash
#!/usr/bin/env bash

MODEL="Sonnet 4.6"
BRANCH=$(git branch --show-current 2>/dev/null || echo "no-git")

# 当前进度
PERCENT=14

FILLED=$((PERCENT / 10))
EMPTY=$((10 - FILLED))

BAR=""

for i in $(seq 1 $FILLED); do
  BAR="${BAR}█"
done

for i in $(seq 1 $EMPTY); do
  BAR="${BAR}░"
done

echo "↑ /gsd:update | $MODEL | $BRANCH | $BAR ${PERCENT}%"
echo "» accept edits on"
```

---

## 3. 添加执行权限

```bash
chmod +x ~/.claude/scripts/statusline-progress.sh
```

---

## 4. 测试输出

```bash
~/.claude/scripts/statusline-progress.sh
```

预期输出：

```text
↑ /gsd:update | Sonnet 4.6 | main | █░░░░░░░░░ 14%
» accept edits on
```

---

## 5. 修改 Claude 配置

编辑：

```bash
nano ~/.claude/settings.json
```

修改为：

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/scripts/statusline-progress.sh",
    "padding": 0,
    "refreshInterval": 5
  }
}
```

---

## 6. 重启 Claude Code

```bash
claude
```

状态栏将显示：

```text
↑ /gsd:update | Sonnet 4.6 | feat/my-feature | █░░░░░░░░░ 14%
» accept edits on
```

---

# 动态进度

## 创建进度文件

```bash
mkdir -p .gsd
echo 14 > .gsd/progress
```

---

## 修改脚本

将：

```bash
PERCENT=14
```

替换为：

```bash
PERCENT=$(cat .gsd/progress 2>/dev/null || echo 0)
```

---

## 更新进度

```bash
echo 35 > .gsd/progress
```

状态栏自动变成：

```text
████░░░░░░ 35%
```

---

# 更高级玩法

可以把进度来源改为：

* Todo 文件完成率
* GitHub Issue 完成率
* Task Master 任务状态
* Agent 队列状态
* Sprint 完成率
* PR Checklist 完成率

例如：

```text
Research    ✓
Design      ✓
Implement   ✓
Test        □
Deploy      □
```

自动计算：

```text
3 / 5 = 60%
```

显示：

```text
██████░░░░ 60%
```

---

# 效果参考

最终状态栏类似：

```text
↑ /gsd:update | Opus 4.6 | agentic-os | ██████░░░░ 60%
» accept edits on
```

这也是 GSD / Agentic-OS 风格状态栏的核心实现思路：通过自定义 `statusLine` 命令动态输出任务进度。
