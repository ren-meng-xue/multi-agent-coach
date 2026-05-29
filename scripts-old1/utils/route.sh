#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TASKS="$ROOT/shared/current/tasks.md"
REVIEW="$ROOT/shared/current/review.md"
PARSE="$ROOT/scripts/utils/parse-task.sh"

if [ ! -f "$TASKS" ]; then
  exit 0
fi

# 提取所有 Task-NNN ID
task_ids=$(perl -ne 'print "$1\n" if /^### (Task-\d+)/' "$TASKS" || true)

if [ -z "$task_ids" ]; then
  exit 0
fi

# 1. 循环依赖检测 (Topological Sort / DFS in Perl)
# 构建依赖图 JSON 传给 Perl
graph_json="{"
for tid in $task_ids; do
  deps=$("$PARSE" "$tid" depends_on 2>/dev/null) || true
  # 提取 ID 部分
  dep_ids=$(echo "$deps" | perl -ne 'print join(",", /Task-\d+/g)')
  graph_json+="\"$tid\":[\"$(echo "$dep_ids" | sed 's/,/","/g')\"],"
done
graph_json="${graph_json%,}}"
# 修正空数组引号问题
graph_json=$(echo "$graph_json" | sed 's/\[""\]/[]/g')

circular_check=$(echo "$graph_json" | perl -MJSON -e '
  my $graph = decode_json(do { local $/; <> });
  my %visited; # 0=unvisited, 1=visiting, 2=visited
  sub has_cycle {
    my $node = shift;
    return 1 if $visited{$node} == 1;
    return 0 if $visited{$node} == 2;
    $visited{$node} = 1;
    for my $dep (@{$graph->{$node} || []}) {
      return 1 if has_cycle($dep);
    }
    $visited{$node} = 2;
    return 0;
  }
  for my $node (keys %$graph) {
    if (has_cycle($node)) {
      print "CYCLE:$node";
      exit;
    }
  }
')

if [[ "$circular_check" =~ ^CYCLE: ]]; then
  echo "ALL -- skipped:circular_dependency ($circular_check)"
  exit 0
fi

# 2. 收集任务信息并排序 (priority desc, created_at asc)
# 优先级映射：high=0, normal=1, low=2
tmp_list=$(mktemp)
for tid in $task_ids; do
  priority=$("$PARSE" "$tid" priority 2>/dev/null || echo "normal")
  created_at=$("$PARSE" "$tid" created_at 2>/dev/null || echo "0000-00-00 00:00")
  
  p_score=1
  [ "$priority" = "high" ] && p_score=0
  [ "$priority" = "low" ] && p_score=2
  
  echo "$p_score|$created_at|$tid" >> "$tmp_list"
done

sorted_task_ids=$(sort -t'|' -k1,1n -k2,2 "$tmp_list" | cut -d'|' -f3)
rm -f "$tmp_list"

# 3. 路由输出
for tid in $sorted_task_ids; do
  state=$("$PARSE" "$tid" state 2>/dev/null) || continue
  type=$("$PARSE" "$tid" type 2>/dev/null) || continue
  owner=$("$PARSE" "$tid" owner 2>/dev/null) || continue
  cancelled=$("$PARSE" "$tid" cancelled 2>/dev/null) || true

  # 跳过终态任务（done 且非 cancelled 需要 planner archive，done+cancelled 跳过）
  if [ "$state" = "done" ] && [ "$cancelled" != "true" ]; then
    echo "$tid planner dispatch (done-&gt;archive)"
    continue
  fi
  [ "$state" = "done" ] && [ "$cancelled" = "true" ] && continue

  # 检查 depends_on
  deps=$("$PARSE" "$tid" depends_on 2>/dev/null) || true
  skip=false
  if [ -n "$deps" ]; then
    IFS=',' read -ra DEP_ARR <<< "$deps"
    for dep in "${DEP_ARR[@]}"; do
      dep=$(echo "$dep" | xargs)
      [ -z "$dep" ] && continue
      dep_id=$(echo "$dep" | awk '{print $1}')
      dep_need=$(echo "$dep" | perl -ne 'print "$1" if /state>=(\w+)/' || echo "done")
      dep_state=$("$PARSE" "$dep_id" state 2>/dev/null) || dep_state="unknown"

      # 状态比较：done > review > in-progress > pending > blocked
      state_order="blocked pending in-progress review done"
      dep_pos=$(echo "$state_order" | tr ' ' '\n' | grep -n "^$dep_state$" | cut -d: -f1 || echo "0")
      need_pos=$(echo "$state_order" | tr ' ' '\n' | grep -n "^$dep_need$" | cut -d: -f1 || echo "0")
      if [ "$dep_pos" -lt "$need_pos" ] 2>/dev/null; then
        echo "$tid -- waiting_on:$dep_id (current=$dep_state, need>=$dep_need)"
        skip=true
        break
      fi
    done
  fi
  [ "$skip" = "true" ] && continue

  # 路由表
  case "$state" in
    pending)
      echo "$tid $owner dispatch (pending-&gt;owner)"
      ;;
    in-progress)
      # owner 继续执行
      echo "$tid $owner dispatch (in-progress-&gt;owner)"
      ;;
    review)
      # 校验 type (trivial/spike/investigate/release/rollback/hotfix 不应进入 review)
      if [[ "$type" =~ ^(trivial|spike|investigate|release|rollback|hotfix)$ ]]; then
        echo "$tid -- skipped:invalid_state_for_type ($state for $type)"
        continue
      fi

      # 检查 review.md 的 decision
      decision=$(awk "/^### $tid/{found=1} found && /^\*\*Decision\*\*:/{print; exit}" "$REVIEW" 2>/dev/null | sed 's/.*Decision\*\*:[[:space:]]*//' || echo "")
      case "$decision" in
        "changes-requested")
          echo "$tid $owner dispatch (review-&gt;changes-requested-&gt;owner)"
          ;;
        "needs-discussion")
          echo "$tid planner dispatch (review-&gt;needs-discussion-&gt;planner)"
          ;;
        "approved")
          echo "$tid planner dispatch (review-&gt;approved-&gt;done)"
          ;;
        *)
          echo "$tid reviewer dispatch (review-&gt;reviewer)"
          ;;
      esac
      ;;
    blocked)
      echo "$tid planner dispatch (blocked-&gt;planner)"
      ;;
    *)
      echo "$tid -- skipped:invalid_state ($state)"
      ;;
  esac
done
