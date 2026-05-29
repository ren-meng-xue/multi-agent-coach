cat > scripts/review-watch.sh <<'EOF'
#!/usr/bin/env bash
set -e

while true; do
  clear
  echo "===== GIT STATUS ====="
  git status --short

  echo
  echo "===== DIFF STAT ====="
  git diff --stat

  echo
  echo "===== CHANGED FILES ====="
  git diff --name-only

  sleep 2
done
EOF