#!/usr/bin/env bash
# Rolls the running marvin1604 VM back to a snapshot taken by snapshot.sh.
# Usage: rollback.sh <tag>   (see `info snapshots` output, or snapshot.sh's stdout)
set -euo pipefail
VM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITOR="$VM_DIR/monitor.sock"
TAG="${1:?usage: rollback.sh <snapshot-tag>}"

if [[ ! -S "$MONITOR" ]]; then
  echo "monitor socket not found at $MONITOR — is the VM running?" >&2
  exit 1
fi

clean() { sed -E 's/\x1b\[[0-9]*[A-Za-z]//g; s/[^[:print:]\t]//g'; }

echo "[*] rolling back to '$TAG'..."
printf 'loadvm %s\n' "$TAG" | socat -t2 - "UNIX-CONNECT:$MONITOR" 2>/dev/null | clean || true
echo "[*] done. VM state restored to snapshot '$TAG'."
