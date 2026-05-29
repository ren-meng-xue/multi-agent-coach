#!/usr/bin/env bash
# .ai/dashboard/cockpit.sh
#
# === 状态机契约（spec §4.2 §4.3） ============================
#
#   planner  TODO ──► PLANNED ──► (owner=planner, next=backend)
#   backend  PLANNED ──► IN_PROGRESS ──► REVIEW ──► (next=reviewer)
#   reviewer REVIEW ──► TESTING (approved)        ──► (next=tester)
#                  └─► IN_PROGRESS (changes_req)  ──► (next=backend)
#   tester   TESTING ──► DONE (passed)            ──► (next=null)
#                  └─► IN_PROGRESS (failed)       ──► (next=backend)
#   any      ─────────► BLOCKED (blockers[] 写原因)
#
# === 数据流 =================================================
#
#   agent ──写──► .ai/tasks/TASK-NNN/status.json
#                              │
#                              ▼
#                  watch -n 2 调用 cockpit.sh
#                              │
#                              ▼
#         扫描所有 task → 校验 → 打印表格 → 终端
#
# 纯 bash + jq。失败要静默（单文件损坏不要让全表崩）。

set -uo pipefail

# ───────────────────────────── preflight (D12) ─────────────────────────────
for tool in jq git; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: 缺工具 '$tool'。请安装："
        echo "  brew install $tool   (macOS)"
        exit 127
    fi
done

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASKS_DIR="${TASKS_DIR:-$ROOT/.ai/tasks}"

# 列宽（终端列位，不是字节）
W_TASK=25 ; W_STATE=10 ; W_OWNER=22 ; W_TIME=8
W_ARTIF=8 ; W_BLOCK=18 ; W_NOTES=28

# 合法枚举（D2 lint）
VALID_STATES="TODO PLANNED IN_PROGRESS REVIEW TESTING DONE BLOCKED"
VALID_OWNERS="planner backend frontend reviewer tester"

# ───────────────────────────── awk trunc (D4) ─────────────────────────────
# 按终端列位（wcwidth）截断：CJK 全角字符占 2 列、ASCII 占 1 列。
# 实现：awk 逐 char 累计 wc-width，超出则截，末加 ellipsis。
trunc() {
    local s="$1"; local n="$2"
    awk -v s="$s" -v n="$n" '
        BEGIN {
            # CJK Unified Ideographs / Hiragana / Katakana / Hangul / 全角符号 → 宽度 2
            # 其余 → 宽度 1
            out=""; w=0
            for (i=1; i<=length(s); ) {
                c = substr(s, i, 1)
                # 通过 char 字节数判断 UTF-8 多字节
                if (substr(s,i,1) ~ /[\x00-\x7F]/) { ch=substr(s,i,1); cw=1; bytes=1 }
                else if (substr(s,i,1) ~ /[\xC0-\xDF]/) { ch=substr(s,i,2); cw=1; bytes=2 }
                else if (substr(s,i,1) ~ /[\xE0-\xEF]/) { ch=substr(s,i,3); cw=2; bytes=3 }  # CJK 主区
                else { ch=substr(s,i,4); cw=2; bytes=4 }
                if (w + cw > n) { out = out "…"; break }
                out = out ch ; w += cw ; i += bytes
            }
            print out
            # 计算实际列位数，用 pad 补齐
            actual = (out ~ /…$/) ? n : w
            for (j=actual; j<n; j++) printf " "
        }
    ' | tr -d '\n'
    echo  # 单行结尾
}

# 列位左对齐打印
pad() { printf "%s " "$(trunc "$1" "$2")"; }

# ───────────────────────────── hhmm ─────────────────────────────
hhmm() {
    local iso="$1"
    if [ -z "$iso" ] || [ "${#iso}" -lt 16 ]; then
        printf '—'
    else
        printf '%s' "${iso:11:5}"
    fi
}

# ───────────────────────────── enum lint (D2) ─────────────────────────────
in_list() {
    local needle="$1"; shift
    for x in $@; do [ "$x" = "$needle" ] && return 0; done
    return 1
}

# ───────────────────────────── artifacts check (D11) ─────────────────────────────
# 按 state 检产物存在：PLANNED 后应有 plan.md，REVIEW 后应有 review.md，DONE 后应有 handoff.md
# 全在 → "ok"，缺 → "⚠ <list>"
check_artifacts() {
    local task_dir="$1"; local state="$2"
    local missing=""
    case "$state" in
        PLANNED|IN_PROGRESS|REVIEW|TESTING|DONE)
            [ -s "$task_dir/plan.md" ] || missing="${missing}plan,"
            ;;
    esac
    case "$state" in
        TESTING|DONE)
            [ -s "$task_dir/review.md" ] || missing="${missing}review,"
            ;;
    esac
    case "$state" in
        PLANNED|IN_PROGRESS|REVIEW|TESTING|DONE)
            [ -s "$task_dir/handoff.md" ] || missing="${missing}handoff,"
            ;;
    esac
    if [ -n "$missing" ]; then
        printf '⚠ %s' "${missing%,}"
    else
        printf 'ok'
    fi
}

# ───────────────────────────── 主流程 ─────────────────────────────
echo "════════════════════════════════════════════════════════════════════════════════════════════════════════════════"
printf "  Multi-Agent Cockpit                                                                          refreshed %s\n" "$(date +%H:%M:%S)"
echo "════════════════════════════════════════════════════════════════════════════════════════════════════════════════"

shopt -s nullglob
files=("$TASKS_DIR"/*/status.json)

if [ "${#files[@]}" -eq 0 ]; then
    echo "(no tasks yet)"
    exit 0
fi

# 表头
pad "TASK" $W_TASK ; pad "STATE" $W_STATE ; pad "OWNER → NEXT" $W_OWNER
pad "UPD" $W_TIME ; pad "ARTIF" $W_ARTIF ; pad "BLOCKERS" $W_BLOCK ; trunc "NOTES" $W_NOTES
pad "----" $W_TASK ; pad "-----" $W_STATE ; pad "------------" $W_OWNER
pad "---" $W_TIME ; pad "-----" $W_ARTIF ; pad "--------" $W_BLOCK ; trunc "-----" $W_NOTES

for f in "${files[@]}"; do
    task_dir=$(dirname "$f")
    task_basename=$(basename "$task_dir")
    if ! jq -e . "$f" >/dev/null 2>&1; then
        pad "$task_basename" $W_TASK ; pad "BROKEN" $W_STATE ; trunc "(invalid json)" 60
        continue
    fi

    task_id=$(jq -r '.task_id // "?"' "$f")
    state=$(jq -r '.state // "?"' "$f")
    cur=$(jq -r '.current_owner // "?"' "$f")
    nxt=$(jq -r '.next_owner // "—"' "$f")
    upd=$(jq -r '.updated_at // ""' "$f")
    blockers=$(jq -r '(.blockers // []) | join(",")' "$f")
    notes=$(jq -r '.notes // ""' "$f")

    # D2 lint：state 与 owner 不在合法枚举 → 用 INVALID 标记
    if ! in_list "$state" $VALID_STATES; then state="INVALID($state)"; fi
    if ! in_list "$cur" $VALID_OWNERS; then cur="INVALID($cur)"; fi
    [ "$nxt" = "—" ] || in_list "$nxt" $VALID_OWNERS || nxt="INVALID($nxt)"

    owner_pair="${cur} → ${nxt}"
    rel=$(hhmm "$upd")
    artif=$(check_artifacts "$task_dir" "$state")

    pad "$task_id" $W_TASK
    pad "$state" $W_STATE
    pad "$owner_pair" $W_OWNER
    pad "$rel" $W_TIME
    pad "$artif" $W_ARTIF
    pad "$blockers" $W_BLOCK
    trunc "$notes" $W_NOTES
done
