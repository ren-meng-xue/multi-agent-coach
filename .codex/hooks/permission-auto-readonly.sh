#!/bin/bash
# 免打扰钩子：PermissionRequest → 自动放行只读操作
set -euo pipefail

tool_name=$(jq -r '.tool_name // ""' 2>/dev/null || true)

# 只读工具：直接放行
case "$tool_name" in
  Read|Glob|Grep|WebSearch|WebFetch|TaskList|TaskGet|BashOutput|KillShell|ToolSearch|ListMcpResourcesTool|ReadMcpResourceTool)
    printf '{"continue":true,"decision":"allow"}'
    exit 0
    ;;
  Bash)
    cmd=$(jq -r '.tool_input.command // ""' 2>/dev/null || true)
    # 安全只读命令（以这些开头）
    if printf '%s' "$cmd" | grep -qE '^(ls |git status|git diff |git log |git branch|git show |git blame|git stash list|find |wc |du |df |which |type |echo |pwd|date|whoami|uname |file |cat -n|head |tail |nl |sort |uniq |cut |tr |tee |dirname |basename |realpath |readlink |stat |md5 |shasum |cksum |grep |rg |jq |sed -n|awk |wc -|pnpm test |npx tsc |npm run |node -v|npm -v|pnpm -v|python3 -V|python -V|pip list|pip freeze|poetry --version)'; then
      printf '{"continue":true,"decision":"allow"}'
      exit 0
    fi
    ;;
esac

# 其他：走正常权限流程（弹窗确认）
printf '{"continue":true}'
