#!/usr/bin/env bash
# Boots the marvin1604 VM (Ubuntu 16.04, EOL, being kept alive out of spite).
# Idempotent: if the VM is already running (per pidfile), does nothing.
set -euo pipefail

VM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISK="$VM_DIR/disk.qcow2"
SEED="$VM_DIR/seed.iso"
PIDFILE="$VM_DIR/qemu.pid"
LOGFILE="$VM_DIR/serial.log"
SSH_PORT=2622

if [[ ! -f "$DISK" ]]; then
  echo "disk.qcow2 not found in $VM_DIR — run the provisioning steps first" >&2
  exit 1
fi

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "VM already running (pid $(cat "$PIDFILE")), ssh port $SSH_PORT"
  exit 0
fi
rm -f "$PIDFILE"

qemu-system-x86_64 \
  -name marvin1604 \
  -enable-kvm \
  -cpu host \
  -m 1536 \
  -smp 2 \
  -drive file="$DISK",if=virtio,format=qcow2 \
  -drive file="$SEED",if=virtio,format=raw,readonly=on \
  -netdev user,id=net0,hostfwd=tcp::${SSH_PORT}-:22 \
  -device virtio-net-pci,netdev=net0 \
  -display none \
  -serial file:"$LOGFILE" \
  -pidfile "$PIDFILE" \
  -daemonize

sleep 1
echo "VM booting (pid $(cat "$PIDFILE")). SSH will become available on 127.0.0.1:${SSH_PORT} once cloud-init finishes (~30-90s on first boot)."
echo "Serial console log: $LOGFILE"
