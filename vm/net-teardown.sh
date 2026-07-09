#!/usr/bin/env bash
# Reverts everything net-setup.sh did (leaves the systemd-networkd bridge/tap
# files in place -- delete /etc/systemd/network/marvin* separately if wanted).
set -euo pipefail
UPLINK="${UPLINK:-ens33}"
VM_IP="${VM_IP:-10.20.0.2}"
if [[ $EUID -ne 0 ]]; then exec sudo -E "$0" "$@"; fi

BEFORE=/etc/ufw/before.rules
if grep -qF '# BEGIN marvin1604 nat' "$BEFORE"; then
  echo "[*] removing NAT stanza from $BEFORE"
  cp "$BEFORE" "$BEFORE.bak-marvin-teardown-$(date +%Y%m%d%H%M%S)"
  sed -i '/# BEGIN marvin1604 nat/,/# END marvin1604 nat/d' "$BEFORE"
fi

echo "[*] deleting ufw route rules (ignore errors if absent)"
ufw --force route delete allow in on "$UPLINK" out on marvinbr0 to "$VM_IP" port 22 proto tcp || true
ufw --force route delete allow in on marvinbr0 out on "$UPLINK" || true

rm -f /etc/sysctl.d/99-marvin-forward.conf
echo "[*] reloading ufw"
ufw reload
echo "[*] teardown complete (ip_forward left as-is until reboot; set to 0 manually if desired)"
