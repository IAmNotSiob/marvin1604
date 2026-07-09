#!/usr/bin/env bash
# Boots the marvin1604 VM (Ubuntu 16.04, EOL, being kept alive out of spite).
# Idempotent: if the VM is already running (per pidfile), does nothing.
set -euo pipefail

VM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISK="$VM_DIR/disk.qcow2"
SEED="$VM_DIR/seed.iso"
PIDFILE="$VM_DIR/qemu.pid"
LOGFILE="$VM_DIR/serial.log"
# marvin is on a host-routed bridge (marvinbr0). It gets a real presence at
# 10.20.0.2; the host is 10.20.0.1. Public internet SSH reaches it via host-side
# DNAT of port 22 (see net-setup.sh), which preserves attacker source IPs so
# fail2ban in the guest can ban them. The agent administers it over the same
# bridge from 10.20.0.1 (whitelisted in fail2ban). The tap device (marvintap)
# is created declaratively by systemd-networkd.
TAP=marvintap
VM_IP=10.20.0.2

if [[ ! -f "$DISK" ]]; then
  echo "disk.qcow2 not found in $VM_DIR — run the provisioning steps first" >&2
  exit 1
fi

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "VM already running (pid $(cat "$PIDFILE")), ssh $VM_IP (admin from 10.20.0.1), public via host DNAT :22"
  exit 0
fi
rm -f "$PIDFILE"

if [[ ! -d "/sys/class/net/$TAP" ]]; then
  echo "tap $TAP does not exist — run net-setup.sh / networkctl first" >&2
  exit 1
fi

qemu-system-x86_64 \
  -name marvin1604 \
  -enable-kvm \
  -cpu host \
  -m 1536 \
  -smp 2 \
  -drive file="$DISK",if=virtio,format=qcow2 \
  -drive file="$SEED",if=virtio,format=raw,readonly=on \
  -netdev tap,id=net0,ifname="$TAP",script=no,downscript=no \
  -device virtio-net-pci,netdev=net0 \
  -display none \
  -serial file:"$LOGFILE" \
  -pidfile "$PIDFILE" \
  -daemonize

sleep 1
echo "VM booting (pid $(cat "$PIDFILE")). SSH: $VM_IP. Public SSH reaches it via host DNAT of port 22 (net-setup.sh)."
echo "Serial console log: $LOGFILE"
