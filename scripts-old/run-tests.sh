#!/usr/bin/env bash
set +e

if [ -f package.json ]; then
  if command -v pnpm >/dev/null 2>&1 && [ -f pnpm-lock.yaml ]; then
    pnpm test
    exit $?
  elif command -v npm >/dev/null 2>&1; then
    npm test
    exit $?
  fi
elif [ -f pyproject.toml ] || [ -f pytest.ini ]; then
  pytest
  exit $?
elif [ -f Cargo.toml ]; then
  cargo test
  exit $?
elif [ -f go.mod ]; then
  go test ./...
  exit $?
fi

echo "No known test config found"
exit 0