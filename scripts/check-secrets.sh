#!/usr/bin/env bash
# Pre-commit guard for this PUBLIC repo: blocks commits that add secret files or key-like strings.
# Installed by `pnpm install` (root "prepare" script sets core.hooksPath=.githooks).
set -euo pipefail

fail=0

# 1. Secret files staged (allow *.example templates).
bad_files=$(git diff --cached --name-only --diff-filter=ACR \
  | grep -E '(^|/)(\.env(\..+)?|\.dev\.vars(\..+)?|service-account[^/]*\.json|credentials[^/]*\.json|[^/]+\.(pem|key|p12))$' \
  | grep -vE '\.example$' || true)
if [ -n "$bad_files" ]; then
  echo "✖ Refusing to commit secret files:" >&2
  echo "$bad_files" | sed 's/^/    /' >&2
  fail=1
fi

# 2. Key-like strings in added lines.
patterns='AIza[0-9A-Za-z_-]{35}|-----BEGIN ([A-Z]+ )?PRIVATE KEY-----|"private_key"[[:space:]]*:|ya29\.[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9]{32,}|ghp_[A-Za-z0-9]{36}'
hits=$(git diff --cached -U0 --diff-filter=ACMR | grep -E '^\+[^+]' | grep -nE "$patterns" || true)
if [ -n "$hits" ]; then
  echo "✖ Possible secret in staged changes:" >&2
  echo "$hits" | cut -c1-120 | sed 's/^/    /' >&2
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "Remove it from the commit (git restore --staged <file>). If a real key was ever pushed, rotate it immediately." >&2
  exit 1
fi
