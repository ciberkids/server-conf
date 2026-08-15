#!/usr/bin/env python3
"""
monitoring-watchdog — cross-host dead-man's-switch for Optimus Prime's monitoring stack.

WHY THIS EXISTS
On 2026-08-14, four services (warracker, firefly-iii, affine, opensign) were found to have
been unreachable for ~4 months. The monitoring had detected it correctly the entire time:
blackbox probes ran, probe_success was 0, and the ServiceDown rule fired. But Alertmanager's
Telegram bot token had been revoked, so every notification failed with 401 and NOTHING was
ever delivered. That failure is observable only in Alertmanager's own container logs, which
nobody reads -- because the whole point of alerting is not having to.

So: "no alerts" was indistinguishable from "no problems". This closes that gap.

WHY IT RUNS ON BUMBLEBEE
A monitor must not share a fate with what it monitors. Prometheus, Alertmanager, Traefik and
Home Assistant all run on Optimus Prime; anything watching them from OP dies with them.

TRANSPORTS (deliberately two, with different failure modes)
  primary  : HA webhook -> mobile-app push. A different transport from Telegram, so it still
             works when the Telegram bot token is dead -- the exact failure found above.
  fallback : bumblebee's own telegram-send. Works when OP is down (and therefore HA with it).
Between them, only a whole-site outage defeats both. That residual gap needs a third-party
heartbeat service and is deliberately out of scope here.

WHAT IT CHECKS
  1. Prometheus is alive AND actually scraping (a live-but-idle Prometheus alerts on nothing).
  2. Alertmanager is alive.
  3. Alertmanager notification FAILURES are not increasing -- this is the check that would
     have caught the 401. Counters reset on restart, so a decrease is treated as a reset,
     never as an alert.
  4. Reports how many alerts are firing, for context in the message.

Logs a POSITIVE line ("healthy - ...") on every run. An error-only log cannot distinguish
"working" from "not running at all".
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

OP = "192.168.1.10"
PROM = f"http://{OP}:9092"
ALERTMGR = f"http://{OP}:9093"
HA_WEBHOOK_BASE = f"http://{OP}:8123/api/webhook"
TELEGRAM_SEND = "/usr/local/bin/telegram-send"
TELEGRAM_CONF = "/etc/telegram-send.conf"   # bumblebee keeps it here, NOT in ~/.config
STATE_DIR = os.environ.get("STATE_DIRECTORY", "/var/lib/monitoring-watchdog")
STATE_F = os.path.join(STATE_DIR, "state.json")
COOLDOWN_S = 4 * 3600         # don't re-nag about an unchanged problem more often than this
MIN_TARGETS_UP = 5            # a healthy OP has dozens; <5 means scraping is broken
TIMEOUT = 10


def log(m):
    print(f"[monitoring-watchdog] {m}", flush=True)


def get(url, timeout=TIMEOUT):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def prom_scalar(query):
    """Run an instant query, return the first sample's value as float, or None."""
    url = f"{PROM}/api/v1/query?query={urllib.parse.quote(query)}"
    d = json.loads(get(url))
    res = d.get("data", {}).get("result") or []
    if not res:
        return None
    return float(res[0]["value"][1])


def am_notification_counters():
    """Sum of telegram notification totals/failures from Alertmanager's own metrics."""
    total = failed = 0.0
    for line in get(f"{ALERTMGR}/metrics").splitlines():
        if line.startswith("alertmanager_notifications_total{"):
            total += float(line.rsplit(" ", 1)[1])
        elif line.startswith("alertmanager_notifications_failed_total{"):
            failed += float(line.rsplit(" ", 1)[1])
    return total, failed


def load_state():
    try:
        with open(STATE_F) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(s):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_F + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f)
    os.replace(tmp, STATE_F)


def notify(title, message):
    """HA push first; fall back to bumblebee's telegram-send. Returns list of transports used."""
    sent = []
    wid = os.environ.get("HA_WEBHOOK_ID")
    if wid:
        try:
            body = json.dumps({"title": title, "message": message}).encode()
            req = urllib.request.Request(
                f"{HA_WEBHOOK_BASE}/{wid}", data=body,
                headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=TIMEOUT)
            sent.append("ha-push")
        except Exception as e:
            log(f"HA webhook failed ({e}) - falling back to telegram")
    else:
        log("HA_WEBHOOK_ID not set - skipping HA push")

    if not sent:  # only bother Telegram if the primary transport failed
        try:
            subprocess.run([TELEGRAM_SEND, "--config", TELEGRAM_CONF,
                            f"{title}\n\n{message}"], check=True, timeout=30)
            sent.append("telegram")
        except Exception as e:
            log(f"telegram-send fallback ALSO failed: {e}")
    return sent


def main():
    check_only = "--check" in sys.argv
    issues, notes = [], []

    # --- 1/2. is the stack even alive? ------------------------------------------------
    prom_up = am_up = False
    try:
        get(f"{PROM}/-/healthy", 8)
        prom_up = True
    except Exception as e:
        issues.append(f"Prometheus unreachable on {PROM} ({type(e).__name__})")
    try:
        get(f"{ALERTMGR}/-/healthy", 8)
        am_up = True
    except Exception as e:
        issues.append(f"Alertmanager unreachable on {ALERTMGR} ({type(e).__name__})")

    # --- 1b. alive but idle is still broken ------------------------------------------
    targets_up = firing = None
    if prom_up:
        try:
            targets_up = prom_scalar("count(up == 1)")
            if targets_up is None or targets_up < MIN_TARGETS_UP:
                issues.append(f"Prometheus is up but only {targets_up} targets are UP "
                              f"(<{MIN_TARGETS_UP}) - scraping looks broken")
            firing = prom_scalar('count(ALERTS{alertstate="firing"})') or 0
            notes.append(f"{int(targets_up or 0)} targets up, {int(firing)} alerts firing")
        except Exception as e:
            issues.append(f"Prometheus query API failing ({type(e).__name__})")

    # --- 3. THE check that would have caught the 401 ----------------------------------
    state = load_state()
    if am_up:
        try:
            total, failed = am_notification_counters()
            prev_failed = state.get("am_failed")
            # Only a genuine INCREASE is a fault. A decrease means Alertmanager restarted
            # and its counters reset -- alerting on that would fire after every update.
            if prev_failed is not None and failed > prev_failed:
                issues.append(
                    f"Alertmanager notification FAILURES rising ({prev_failed:.0f} -> "
                    f"{failed:.0f}): alerts are firing but not being delivered")
            state["am_failed"], state["am_total"] = failed, total
            notes.append(f"notify total={total:.0f} failed={failed:.0f}")
        except Exception as e:
            issues.append(f"Could not read Alertmanager metrics ({type(e).__name__})")

    summary = "; ".join(notes) if notes else "no data"

    if not issues:
        log(f"healthy - {summary}")
        state.pop("last_sig", None)
        state.pop("last_alert_ts", None)
        if not check_only:
            save_state(state)
        return

    sig = " | ".join(sorted(issues))
    log(f"PROBLEMS: {sig} ({summary})")
    if check_only:
        log("--check mode - not notifying")
        return

    now = time.time()
    if state.get("last_sig") == sig and now - state.get("last_alert_ts", 0) < COOLDOWN_S:
        log("same problem within cooldown - not re-notifying")
        save_state(state)
        return

    body = ("\n".join(f"- {i}" for i in issues)
            + f"\n\nContext: {summary}."
            + "\n\nThis watchdog runs on Bumblebee precisely so it survives Optimus Prime's"
              " monitoring being down. If you are reading this, check Prometheus/Alertmanager"
              " on OP - alerts from OP itself may not be reaching you.")
    used = notify("\U0001F6A8 Monitoring stack problem on Optimus Prime", body)
    log(f"notified via: {used or 'NOTHING - all transports failed'}")
    state["last_sig"], state["last_alert_ts"] = sig, now
    save_state(state)
    if not used:
        sys.exit(1)   # let OnFailure= fire; nothing got through


if __name__ == "__main__":
    main()
