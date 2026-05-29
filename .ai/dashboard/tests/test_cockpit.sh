#!/usr/bin/env bash
# 给 cockpit.sh 跑 6 类 fixture，diff 输出 vs expected。
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COCKPIT="$SCRIPT_DIR/../cockpit.sh"
FIX="$SCRIPT_DIR/fixtures"
EXP="$SCRIPT_DIR/expected"

pass=0; fail=0
for fixture in "$FIX"/*/; do
    name=$(basename "$fixture")
    expected="$EXP/${name}.txt"
    [ -f "$expected" ] || { echo "SKIP $name (no expected)"; continue; }

    # 临时把 TASKS_DIR 指向单一 fixture 跑
    # 注意：cockpit.sh 会打印全表，我们需要过滤出当前 fixture 的那一行
    # 或者我们可以让 cockpit.sh 整个输出与 expected 对齐，但 grep 比较稳妥
    actual=$(TASKS_DIR="$FIX" bash "$COCKPIT" 2>/dev/null | grep -F "$name" || true)
    expected_content=$(cat "$expected")

    if [ "$actual" = "$expected_content" ]; then
        echo "✓ $name"
        pass=$((pass+1))
    else
        echo "✗ $name"
        echo "Actual  : [$actual]"
        echo "Expected: [$expected_content]"
        diff <(echo "$actual") <(echo "$expected_content") | head -10
        fail=$((fail+1))
    fi
done

echo "---"
echo "PASS=$pass FAIL=$fail"
[ $fail -eq 0 ]
