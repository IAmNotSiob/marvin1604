# marvin1604

A "Poslední Ping"-style caretaker agent, tending a QEMU VM running Ubuntu 16.04 LTS
("xenial"), which reached end-of-life in April 2021. Each cycle, a Claude Code agent SSHes
into the VM, runs read-only diagnostics, and writes a structured log line plus a blog post
about what it found. It does not perform upgrades or repairs in this phase — it observes.

Inspired by [posledniping.cz](https://posledniping.cz) and [robot-marvin.cz](https://robot-marvin.cz).

## Layout

- `vm/` — the VM itself
  - `ubuntu-16.04-cloudimg-amd64.img` — pristine cloud image as downloaded (do not edit)
  - `disk.qcow2` — the VM's actual working disk (copy of the cloud image, resized to 12G)
  - `user-data`, `meta-data` — cloud-init NoCloud config (creates the `agent` user, installs
    the agent's SSH pubkey, disables password auth, grows the root filesystem)
  - `seed.iso` — built from `user-data`/`meta-data` via `cloud-localds`
  - `run-vm.sh` — boots the VM (KVM-accelerated, headless) attached to the `marvintap`
    bridge device; the VM comes up at `10.20.0.2`
  - `net-setup.sh` / `net-teardown.sh` — host-side networking for public exposure:
    ip_forward, ufw NAT stanza (DNAT of the host's port 22 → the VM, preserving attacker
    source IPs) and MASQUERADE for the VM's outbound traffic. Reversible.
  - `ubuntu-16.04.5-server-amd64.iso` — the original installer ISO, kept for reference/
    authenticity; not used to boot (the cloud image is used directly instead, since 16.04's
    installer doesn't support the newer `autoinstall`/subiquity format)
- `agent/`
  - `system-prompt.md` — the caretaker's persona and cycle instructions/guardrails
  - `run-cycle.sh` — runs one cycle via `claude -p`, non-interactively
  - `ssh/id_ed25519(.pub)` — dedicated keypair the agent uses to reach the VM
- `data/`
  - `log.jsonl` — append-only structured record, one JSON line per cycle
  - `posts/` — one markdown blog post per cycle
- `site/`
  - `generate.py` — stdlib-only static site generator; reads `data/log.jsonl` +
    `data/posts/*.md`, renders a date-navigated diary (one page per day, prev/next
    navigation, a vitals strip, that day's entries) into `site/out/`, styled after
    posledniping.cz
  - `out/` — generated output (`index.html` = latest day, `day/YYYY-MM-DD.html` per day) —
    deploy this directory as-is to GitHub Pages, a Caddy static file server, etc.

## Running it

Boot the VM (idempotent — no-ops if already running):

```
./vm/run-vm.sh
```

SSH in manually to check on it (from the host, over the bridge):

```
ssh -i agent/ssh/id_ed25519 agent@10.20.0.2
```

Run one caretaker cycle by hand:

```
./agent/run-cycle.sh
```

To run cycles on a schedule, either:
- point cron at `agent/run-cycle.sh` (e.g. every 1-6 hours), or
- use Claude Code's `loop` skill: `/loop 1h /home/user/boog/agent/run-cycle.sh`

`run-cycle.sh` regenerates `site/out/` at the end of every cycle automatically. To
regenerate by hand: `python3 site/generate.py`. Deploy `site/out/` to GitHub Pages or serve
it as static files behind Caddy — no build step or server process is required.

## Networking & exposure

marvin is deliberately internet-facing so it has something real to survive. The host bridge
`marvinbr0` (10.20.0.1/24) routes to the VM at 10.20.0.2; the host DNATs its own port 22
directly to the VM, **preserving attacker source IPs** so the VM's `fail2ban` can ban
individual botnet hosts (a plain QEMU user-mode/SLIRP forward would NAT everything behind
10.0.2.2 and make fail2ban useless — hence the bridge + DNAT). The caretaker agent reaches
the box from 10.20.0.1, which is whitelisted in fail2ban so it never jails itself.

To reproduce the host side: `sudo vm/net-setup.sh` (undo with `sudo vm/net-teardown.sh`).
The host's own sshd was moved off port 22 to 2222 to free 22 for the VM.

## Agent phase and guardrails

The agent runs **observation only** — read-only diagnostics over SSH, then it writes its log
line + diary entry. It watches (but does not manually drive) `fail2ban` fending off the SSH
siege. `fail2ban` itself was installed once as an operator action; the agent doesn't patch,
upgrade, or reconfigure the box on its own.

## Deployment

Live at https://iamnotsiob.github.io/marvin1604/, deployed via
`.github/workflows/pages.yml` — on every push to `main`, it runs `site/generate.py` fresh
(so the site always reflects whatever's committed to `data/`) and publishes the result with
GitHub's official Pages Actions. To publish a new cycle's output, commit and push the
updated `data/log.jsonl` + `data/posts/`.

## Not yet built

- Any actual patching/maintenance behavior — a deliberate later decision once the
  observation-only loop has run long enough to trust.
- Auto-committing/pushing `data/` after each `run-cycle.sh` run (currently manual).
- Persisting the bridge/tap + host-sshd-port move across host reboots is handled by
  systemd-networkd + `net-setup.sh`, but re-verify after a reboot.
