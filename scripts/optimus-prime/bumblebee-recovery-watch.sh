#!/bin/bash
# Watch a WEDGED bumblebee for an SSH window and, if one opens, recover it.
#
# Context: 2026-08-21 09:26 bumblebee wedged with the kernel alive (ICMP replies, TCP
# handshakes complete) but ALL userspace dead including sshd -- ssh dies "during banner
# exchange". There was one brief recovery at 09:25 (a single Prometheus scrape got
# through), which is the entire reason a polling retry is worth running at all.
#
# 🔑 DESIGN: EVIDENCE BEFORE REBOOT. If a window opens it may last seconds, and a reboot
# destroys exactly the kernel ring buffer that explains the wedge. So capture first, to a
# file ON THIS HOST (bumblebee's own disk is the prime suspect), and only then reset.
#
# Notifies on STATE CHANGE only -- never once per tick. A 5-minute Telegram drip would be
# noise, and noise is how real alerts get ignored.

TARGET=192.168.1.14
STATE_DIR=/var/lib/bumblebee-recovery
STAMP=$(date +%Y%m%d-%H%M%S)
EVIDENCE="$STATE_DIR/evidence-$STAMP.txt"
DONE_FLAG="$STATE_DIR/done"
SKIP_REBOOT_FLAG="$STATE_DIR/no-reboot"   # touch this to capture evidence but NOT reset
LOG="$STATE_DIR/watch.log"

mkdir -p "$STATE_DIR"
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }
notify(){ /usr/bin/telegram-send "$1" >/dev/null 2>&1 || log "telegram-send FAILED"; }

# Already finished its job -- do nothing (belt and braces; the timer is also disabled).
[ -e "$DONE_FLAG" ] && exit 0

# --- Deadline: give up after DEADLINE_HOURS and SAY SO -------------------------------
# A watcher that runs forever in silence is worse than one that reports giving up: the
# absence of messages would read as "still trying" when it might have died months ago.
DEADLINE_HOURS=4
START_FLAG="$STATE_DIR/started-at"
[ -e "$START_FLAG" ] || date +%s > "$START_FLAG"
ELAPSED=$(( $(date +%s) - $(cat "$START_FLAG") ))
if [ "$ELAPSED" -gt $(( DEADLINE_HOURS * 3600 )) ]; then
    log "deadline reached (${DEADLINE_HOURS}h) with no SSH window; giving up"
    notify "[optimus-prime] 🛑 Gave up on bumblebee after ${DEADLINE_HOURS}h — no SSH window ever opened, it is still wedged (kernel replies to ping, userspace dead). It needs a PHYSICAL power cycle. After it boots, run FIRST: journalctl -b -1 -k | grep -iE 'nvme|i/o error|timeout|reset|hung task' and smartctl -a /dev/nvme0"
    touch "$DONE_FLAG"
    systemctl disable --now bumblebee-recovery-watch.timer >/dev/null 2>&1
    exit 0
fi

# --- 0. Is it reachable at all? -------------------------------------------------------
if ! ping -c 2 -W 2 "$TARGET" >/dev/null 2>&1; then
    log "no ICMP response (previously it DID reply -- state changed)"
    exit 0
fi

# --- 1. Did it recover on its own? ----------------------------------------------------
# node-exporter answering means userspace is genuinely back, not just the kernel.
if curl -sf -m 8 -o /dev/null "http://$TARGET:9100/metrics" 2>/dev/null; then
    log "RECOVERED on its own: node-exporter is answering"
    notify "[optimus-prime] ✅ bumblebee RECOVERED on its own — node-exporter is answering. No reboot issued. Recovery watch disabled."
    touch "$DONE_FLAG"
    systemctl disable --now bumblebee-recovery-watch.timer >/dev/null 2>&1
    exit 0
fi

# --- 2. Try to get a shell. Several identities, because which key bumblebee accepts -----
#         from THIS host has never been verified (it was already wedged when this was
#         written), so a single-key attempt would be a single point of failure.
SSH_OPTS="-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
-o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
GOT_IN=""
for key in ~/.ssh/home-server/id_rsa ~/.ssh/optimusprime_id_rsa ""; do
    ident=""; [ -n "$key" ] && [ -r "$key" ] && ident="-i $key"
    if timeout 25 ssh $SSH_OPTS $ident "$TARGET" 'true' 2>/dev/null; then
        GOT_IN="$ident"; break
    fi
done

if [ -z "$GOT_IN" ]; then
    log "still wedged (ping ok, ssh refused/timed out)"
    exit 0
fi

# --- 3. WE ARE IN. Capture evidence FIRST, before anything can take it away ------------
log "SSH WINDOW OPEN (identity: ${GOT_IN:-default}) -- capturing evidence"
notify "[optimus-prime] 🟡 bumblebee accepted SSH — capturing diagnostics before any reset."

{
  echo "===== captured $(date '+%F %T') from optimusprime ====="
  for cmd in \
    "uptime" \
    "uptime -s" \
    "systemctl is-system-running" \
    "systemctl --failed --no-legend --plain" \
    "cat /proc/mdstat" \
    "df -h -x tmpfs -x devtmpfs" \
    "free -m" \
    "sudo -n dmesg -T | tail -400" \
    "sudo -n journalctl -k -b 0 --no-pager | grep -iE 'nvme|i/o error|timeout|reset|hung task|EXT4-fs|XFS' | tail -200" \
    "sudo -n smartctl -a /dev/nvme0" \
    "sudo -n podman ps -a --format '{{.Names}} {{.Status}}'"
  do
    echo; echo "----- \$ $cmd -----"
    timeout 45 ssh $SSH_OPTS $GOT_IN "$TARGET" "$cmd" 2>&1 || echo "(command failed or timed out)"
  done
} >> "$EVIDENCE"

log "evidence written to $EVIDENCE ($(wc -l < "$EVIDENCE") lines)"
notify "[optimus-prime] 📄 bumblebee diagnostics captured to $EVIDENCE ($(wc -l < "$EVIDENCE") lines)."

# --- 4. Decide whether to reset -------------------------------------------------------
if [ -e "$SKIP_REBOOT_FLAG" ]; then
    log "no-reboot flag present; stopping after capture"
    notify "[optimus-prime] ⏸ bumblebee: evidence captured, reboot SKIPPED (no-reboot flag set)."
    touch "$DONE_FLAG"; exit 0
fi

RUNNING=$(timeout 20 ssh $SSH_OPTS $GOT_IN "$TARGET" "sudo -n podman ps -q 2>/dev/null | wc -l" 2>/dev/null || echo "?")
SYSSTATE=$(timeout 20 ssh $SSH_OPTS $GOT_IN "$TARGET" "systemctl is-system-running 2>/dev/null" 2>/dev/null || echo "?")
log "post-capture health: containers=$RUNNING systemd=$SYSSTATE"

if [ "$RUNNING" = "21" ] && [ "$SYSSTATE" = "running" ]; then
    log "host looks fully healthy -- NOT rebooting"
    notify "[optimus-prime] ✅ bumblebee is back and healthy (21 containers, systemd running). No reboot issued."
    touch "$DONE_FLAG"
    systemctl disable --now bumblebee-recovery-watch.timer >/dev/null 2>&1
    exit 0
fi

# --- 5. Reset. Clean reboot first; sysrq only if that hangs ---------------------------
# `systemctl reboot` needs to exec from disk, which is what may be broken -- so give it a
# short leash, then fall back to magic SysRq, which is handled entirely in-kernel and
# needs no disk at all. 's' (sync) is attempted separately so a hung sync cannot block
# the reset; the box has not written anything for hours, so skipping it risks little.
notify "[optimus-prime] 🔁 bumblebee still unhealthy (containers=$RUNNING, systemd=$SYSSTATE) — issuing reboot."
log "attempting clean reboot"
# Whether matteo has NOPASSWD sudo on bumblebee has never been verified (it was already
# wedged when this was written), so try sudo -n first and plain systemctl second -- polkit
# may permit the latter. `sudo -n` fails fast instead of waiting on a password prompt.
timeout 40 ssh $SSH_OPTS $GOT_IN "$TARGET" "sudo -n systemctl reboot || systemctl reboot" 2>/dev/null
sleep 25

if ping -c 2 -W 2 "$TARGET" >/dev/null 2>&1 && timeout 20 ssh $SSH_OPTS $GOT_IN "$TARGET" 'true' 2>/dev/null; then
    log "still up after clean reboot request -- escalating to magic SysRq"
    notify "[optimus-prime] ⚠️ bumblebee ignored the clean reboot — escalating to SysRq reset."
    timeout 20 ssh $SSH_OPTS $GOT_IN "$TARGET" "sudo -n sysctl -w kernel.sysrq=1" 2>/dev/null
    timeout 10 ssh $SSH_OPTS $GOT_IN "$TARGET" "echo s | sudo -n tee /proc/sysrq-trigger" 2>/dev/null
    timeout 10 ssh $SSH_OPTS $GOT_IN "$TARGET" "echo b | sudo -n tee /proc/sysrq-trigger" 2>/dev/null
fi

log "reset issued; disabling watch"
notify "[optimus-prime] 🔁 bumblebee reset issued. Evidence is at $EVIDENCE on optimusprime. Watch disabled — re-enable with: systemctl enable --now bumblebee-recovery-watch.timer"
touch "$DONE_FLAG"
systemctl disable --now bumblebee-recovery-watch.timer >/dev/null 2>&1
exit 0
