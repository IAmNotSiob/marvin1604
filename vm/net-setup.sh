#!/usr/bin/env bash
# Host-side networking for marvin1604's public exposure with REAL source IPs.
#
# Gives marvin a host-routed bridge (marvinbr0 = 10.20.0.1/24, VM at 10.20.0.2)
# and wires iptables so that internet SSH hitting the host's port 22 is DNAT'd
# straight to the VM with the original source IP preserved -- which is what lets
# fail2ban inside the VM actually ban individual attackers. Marvin's outbound
# traffic is MASQUERADEd out the host uplink.
#
# The bridge/tap themselves are defined declaratively in /etc/systemd/network/
# (marvinbr0.netdev, marvinbr0.network, marvintap.netdev, marvintap.network).
# This script only handles the parts systemd-networkd doesn't: ip_forward and
# the ufw NAT/forward rules. Idempotent. See net-teardown.sh to undo.
set -euo pipefail

UPLINK="${UPLINK:-ens33}"          # host's internet-facing interface
VM_IP="${VM_IP:-10.20.0.2}"
SUBNET="${SUBNET:-10.20.0.0/24}"
PUBLIC_SSH_PORT="${PUBLIC_SSH_PORT:-22}"

if [[ $EUID -ne 0 ]]; then exec sudo -E "$0" "$@"; fi

echo "[*] enabling IPv4 forwarding (persistent)"
sysctl -w net.ipv4.ip_forward=1 >/dev/null
install -d /etc/sysctl.d
echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-marvin-forward.conf

# --- ufw before.rules NAT stanza (survives ufw reloads) -------------------
BEFORE=/etc/ufw/before.rules
MARK_BEGIN='# BEGIN marvin1604 nat'
MARK_END='# END marvin1604 nat'
if ! grep -qF "$MARK_BEGIN" "$BEFORE"; then
  echo "[*] inserting NAT stanza into $BEFORE"
  cp "$BEFORE" "$BEFORE.bak-marvin-$(date +%Y%m%d%H%M%S)"
  TMP=$(mktemp)
  {
    echo "$MARK_BEGIN"
    echo '*nat'
    echo ':PREROUTING ACCEPT [0:0]'
    echo ':POSTROUTING ACCEPT [0:0]'
    echo "-A PREROUTING -i ${UPLINK} -p tcp --dport ${PUBLIC_SSH_PORT} -j DNAT --to-destination ${VM_IP}:22"
    echo "-A POSTROUTING -s ${SUBNET} -o ${UPLINK} -j MASQUERADE"
    echo 'COMMIT'
    echo "$MARK_END"
    cat "$BEFORE"
  } > "$TMP"
  mv "$TMP" "$BEFORE"
else
  echo "[=] NAT stanza already present in $BEFORE"
fi

# --- ufw route (FORWARD) rules -------------------------------------------
echo "[*] adding ufw route rules"
ufw route allow in on "$UPLINK" out on marvinbr0 to "$VM_IP" port 22 proto tcp
ufw route allow in on marvinbr0 out on "$UPLINK"

echo "[*] reloading ufw"
ufw reload

echo "[*] done. verifying NAT rules:"
iptables -t nat -S PREROUTING  | grep -- "--to-destination ${VM_IP}:22" || true
iptables -t nat -S POSTROUTING | grep -- "MASQUERADE" | grep "$SUBNET" || true
