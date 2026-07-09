#!/usr/bin/env bash
# Runs one maintenance/observation cycle of the marvin1604 caretaker agent.
# Intended to be invoked by cron or the `loop` skill on an interval.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PERSONA="$(cat agent/system-prompt.md)"
PROMPT="Run one caretaker cycle for marvin1604 now: SSH in, run read-only diagnostics, then append a log.jsonl line and write a new post to data/posts/. Do not run any state-changing command on the VM."

claude -p "$PROMPT" \
  --append-system-prompt "$PERSONA" \
  --allowedTools "Bash(ssh *) Bash(mkdir *) Write Read" \
  --permission-mode acceptEdits \
  --add-dir "$ROOT"

python3 "$ROOT/site/generate.py"
