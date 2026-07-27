#!/usr/bin/env python3
"""
zigbee-watchdog — detect a partial SLZB-06 coordinator wedge and auto-recover.

Background: the CC2652 radio occasionally wedges at the AF layer — z2m's low-level
SYS heartbeat still succeeds (so z2m keeps the socket open and NEVER self-recovers),
but no Zigbee traffic flows: outbound sends time out (SRSP-AF-dataRequest) and no
device reports arrive. The whole network goes silently dark for hours. The only
known fix is a PoE power-cycle of the SLZB-06 + a z2m restart.

Detection (log-based, no extra deps): a healthy 60-device network publishes many
device messages per minute. If the newest z2m log shows NO non-bridge device
publish for > STALL_MINUTES while the z2m unit is active, the radio is wedged.

Recovery: PoE-cycle the coordinator's switch port (UniFi API) -> restart z2m ->
verify traffic resumed -> Telegram notify. A cooldown prevents power-cycle loops.

Run periodically via zigbee-watchdog.timer. Use `--check` to report status only.
"""
import glob, os, re, sys, time, json, subprocess, urllib.request, ssl
from datetime import datetime

STALL_MINUTES    = 15
COOLDOWN_MINUTES = 30
LOG_GLOB   = "/mnt/data/docker_persistent/zigbee2mqtt/data/log/*/log.log"
COOLDOWN_F = "/run/zigbee-watchdog.cooldown"
TAIL_BYTES = 800_000                 # scan the tail of the (possibly large) log
UNIFI_URL  = "https://192.168.1.1"
SW_MAC     = "24:5a:4c:a0:df:56"     # "Switch Living room" (USL16P)
SW_PORT    = 2                       # SLZB-06 PoE port
PUB_RE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\].*MQTT publish: topic 'zigbee2mqtt/(?!bridge)")

def log(m): print(f"[zigbee-watchdog] {m}", flush=True)

def z2m_active():
    return subprocess.run(["systemctl", "is-active", "--quiet", "zigbee2mqtt"]).returncode == 0

def z2m_uptime_secs():
    """Seconds z2m has been active, via ActiveEnterTimestampMonotonic vs /proc/uptime.
    Returns None if unknown. Used to avoid mistaking a fresh (re)start's not-yet-
    flowing traffic for a wedge."""
    out = subprocess.run(["systemctl", "show", "zigbee2mqtt",
                          "-p", "ActiveEnterTimestampMonotonic", "--value"],
                         capture_output=True, text=True).stdout.strip()
    if not out or out == "0":
        return None
    try:
        active_since_boot = int(out) / 1e6
        with open("/proc/uptime") as f:
            boot_secs = float(f.read().split()[0])
        return boot_secs - active_since_boot
    except (ValueError, OSError):
        return None

def newest_log():
    files = glob.glob(LOG_GLOB)
    return max(files, key=os.path.getmtime) if files else None

def minutes_since_last_device_msg():
    """Return minutes since the last non-bridge device publish, or None if the
    log/tail contains none (which — combined with an old file — means dark)."""
    path = newest_log()
    if not path:
        return None, None
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - TAIL_BYTES))
        tail = f.read().decode("utf-8", "replace")
    last_ts = None
    for line in tail.splitlines():
        m = PUB_RE.match(line)
        if m:
            last_ts = m.group(1)
    if last_ts is None:
        return None, path
    dt = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
    return (datetime.now() - dt).total_seconds() / 60.0, path

def in_cooldown():
    try:
        return (time.time() - os.path.getmtime(COOLDOWN_F)) < COOLDOWN_MINUTES * 60
    except OSError:
        return False

def telegram(msg):
    tok, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return
    try:
        body = json.dumps({"chat_id": chat, "text": msg, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                     data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log(f"telegram failed: {e}")

def poe_cycle():
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    body = json.dumps({"cmd": "power-cycle", "mac": SW_MAC, "port_idx": SW_PORT}).encode()
    req = urllib.request.Request(f"{UNIFI_URL}/proxy/network/api/s/default/cmd/devmgr",
                                 data=body, method="POST",
                                 headers={"X-API-KEY": os.environ["UNIFI_API_KEY"],
                                          "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=15, context=ctx))

def recover():
    # Stamp cooldown FIRST: if a later step throws (UniFi blip, etc.), the next tick
    # still respects the cooldown instead of retrying immediately (no power-cycle spam).
    open(COOLDOWN_F, "w").close(); os.utime(COOLDOWN_F, None)
    telegram("🐕 <b>Zigbee watchdog</b>: coordinator wedge detected "
             f"(no device traffic &gt;{STALL_MINUTES}min). Auto-recovering — PoE-cycling SLZB-06…")
    log("recovering: PoE power-cycle")
    poe_cycle()
    time.sleep(40)                                   # SLZB reboot
    subprocess.run(["systemctl", "reset-failed", "zigbee2mqtt"])
    subprocess.run(["systemctl", "restart", "zigbee2mqtt"])
    # z2m cold start + retained-message flood can take ~90s; poll up to ~2min.
    ok = False
    for _ in range(6):
        time.sleep(20)
        gap, _ = minutes_since_last_device_msg()
        if gap is not None and gap < 2:
            ok = True
            break
    if ok:
        # Don't name a firmware version here. An earlier version of this message pointed at
        # "fw 20260425", which does not exist -- the radio is already on the newest coordinator
        # build (20260311). Verified 2026-07-27; see docs and memory. Cooling is the real lever.
        telegram("✅ <b>Zigbee watchdog</b>: recovered — device traffic resumed. "
                 "⚠️ This is the recurring coordinator wedge (radio ~90 °C) — a stopgap, "
                 "not a fix. Permanent fix = cooling (USB power instead of PoE) / relocation.")
        log("recovery OK")
    else:
        telegram("⚠️ <b>Zigbee watchdog</b>: PoE-cycled + restarted z2m but traffic hasn't "
                 "resumed — needs manual attention (radio ~90 °C; possible harder wedge).")
        log("recovery uncertain")

def main():
    check_only = "--check" in sys.argv
    if not z2m_active():
        log("z2m not active — skipping (not a wedge; z2m is down/updating)")
        return
    # Guard against false-firing during a fresh (re)start: right after z2m starts,
    # the new log legitimately has no device publishes yet (~50-90s). Only treat
    # silence as a wedge once z2m has been up long enough to HAVE traffic history.
    up = z2m_uptime_secs()
    if up is None or up < STALL_MINUTES * 60:
        log(f"z2m active only {up}s (< {STALL_MINUTES}min) — insufficient history, skipping")
        return
    gap, path = minutes_since_last_device_msg()
    log(f"log={path} z2m_uptime={int(up)}s minutes_since_last_device_msg={gap}")
    wedged = (gap is None) or (gap > STALL_MINUTES)
    if not wedged:
        log("healthy — traffic flowing")
        return
    if check_only:
        log(f"WOULD RECOVER (gap={gap}) — --check mode, no action")
        return
    if in_cooldown():
        log("wedge suspected but in cooldown — skipping to avoid loop")
        telegram("🐕 Zigbee watchdog: wedge still suspected but within cooldown — "
                 "not power-cycling again; manual check advised.")
        return
    recover()

if __name__ == "__main__":
    main()
