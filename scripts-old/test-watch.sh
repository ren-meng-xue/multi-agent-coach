cat > scripts/test-watch.sh <<'EOF'
#!/usr/bin/env bash

while true; do
  clear
  echo "===== TEST WATCH ====="
  date
  echo

  if [ -f package.json ]; then
    echo "Detected Node project"
    if command -v pnpm >/dev/null 2>&1 && [ -f pnpm-lock.yaml ]; then
      pnpm test
    elif command -v npm >/dev/null 2>&1; then
      npm test
    else
      echo "No npm/pnpm found"
    fi

  elif [ -f pyproject.toml ] || [ -f pytest.ini ]; then
    echo "Detected Python project"
    pytest

  elif [ -f Cargo.toml ]; then
    echo "Detected Rust project"
    cargo test

  elif [ -f go.mod ]; then
    echo "Detected Go project"
    go test ./...

  else
    echo "No known test config found"
  fi

  echo
  echo "Re-running in 10 seconds..."
  sleep 10
done
EOF