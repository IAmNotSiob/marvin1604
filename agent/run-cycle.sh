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

# Publish: commit the new cycle's data and push. The Pages workflow rebuilds the
# site from data/ on push, so this is what makes a new diary day go live.
# site/out/ is gitignored (built in CI), so only data/ changes get committed.
if [[ -n "$(git -C "$ROOT" status --porcelain data/)" ]]; then
  git -C "$ROOT" add data/
  git -C "$ROOT" commit -q -m "cycle: $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    -m "Automated caretaker cycle." \
    -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
  git -C "$ROOT" push -q && echo "[run-cycle] pushed new cycle data"
else
  echo "[run-cycle] no data changes to publish this cycle"
fi
