#!/usr/bin/env bash
# Takes a live internal snapshot (disk + RAM state) of the running marvin1604 VM
# via the QEMU HMP monitor socket, so risky operations (like Monday's security
# updates) can be rolled back with rollback.sh if something breaks.
set -euo pipefail
VM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONITOR="$VM_DIR/monitor.sock"
TAG="${1:-pre-update-$(date -u +%Y%m%dT%H%M%SZ)}"

if [[ ! -S "$MONITOR" ]]; then
  echo "monitor socket not found at $MONITOR — is the VM running?" >&2
  exit 1
fi

clean() { sed -E 's/\x1b\[[0-9]*[A-Za-z]//g; s/[^[:print:]\t]//g'; }

echo "[*] taking snapshot '$TAG'..." >&2
printf 'savevm %s\n' "$TAG" | socat -t2 - "UNIX-CONNECT:$MONITOR" 2>/dev/null | clean >&2 || true
echo "[*] snapshot list:" >&2
echo "info snapshots" | socat -t2 - "UNIX-CONNECT:$MONITOR" 2>/dev/null | clean >&2
echo "$TAG"
