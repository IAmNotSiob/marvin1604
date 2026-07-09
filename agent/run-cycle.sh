#!/usr/bin/env bash
# Runs one maintenance/observation cycle of the marvin1604 caretaker agent.
# Intended to be invoked by cron or the `loop` skill on an interval.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PERSONA="$(cat agent/system-prompt.md)"
TODAY_DOW="$(date -u +%A)"

if [[ "$TODAY_DOW" == "Monday" ]]; then
  # Hard safety net: snapshot before the agent is allowed to touch anything,
  # regardless of what it decides to do. Not the agent's call — always happens.
  if [[ -S "$ROOT/vm/monitor.sock" ]]; then
    SNAP_TAG=$(vm/snapshot.sh "pre-update-$(date -u +%Y%m%dT%H%M%SZ)" | tail -1)
    echo "[run-cycle] Monday: took pre-maintenance snapshot '$SNAP_TAG'"
  else
    SNAP_TAG="(none — VM monitor socket not found, snapshot skipped)"
    echo "[run-cycle] WARNING: Monday but no monitor.sock — proceeding without a snapshot" >&2
  fi
  PROMPT="Run one caretaker cycle for marvin1604 now. Today is Monday: maintenance is in scope per the persona's Monday rules. A pre-maintenance snapshot was already taken (tag: $SNAP_TAG) before you started. SSH in, observe, and if warranted perform the allowed Monday maintenance (security updates, hardening), then append a log.jsonl line and write a new post to data/posts/."
else
  PROMPT="Run one caretaker cycle for marvin1604 now: SSH in, run read-only diagnostics, then append a log.jsonl line and write a new post to data/posts/. Do not run any state-changing command on the VM."
fi

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
