#!/usr/bin/env python3
"""Publish cumulative amdgpu per-engine busy time from DRM fdinfo as Prometheus counters.

Reads /proc/<pid>/fdinfo/<fd> for every open amdgpu DRM fd, deduplicates by
drm-client-id (one client exposes the same counters on several fds), and
accumulates per-engine nanoseconds into a monotonic host-level total that
survives client exit.  Requires root: fdinfo of a root-owned process is
unreadable as a normal user and yields a silent zero.
"""
import json, os, re, sys, tempfile

def discover_card():
    """Find the amdgpu card and its PCI address by asking the DRIVER, not by guessing.

    The predecessor of this script hardcoded `card0` (the GPU is card1) and published a
    plausible-looking 0 for four months because `${VAR:-0}` masked the missing file. Never
    hardcode the index or the PCI address: derive both, and fail loudly if neither is found.
    """
    for entry in sorted(os.listdir("/sys/class/drm")):
        if not re.fullmatch(r"card\d+", entry):
            continue
        dev = f"/sys/class/drm/{entry}/device"
        try:
            if os.path.basename(os.path.realpath(f"{dev}/driver")) != "amdgpu":
                continue
        except OSError:
            continue
        # /sys/.../0000:0b:00.0 -> the PCI address is the leaf of the resolved device path
        return entry, os.path.basename(os.path.realpath(dev))
    return None, None


if os.geteuid() != 0:
    # fdinfo of a root-owned process is unreadable as a normal user and scan() swallows the
    # OSError, so a non-root run publishes a PLAUSIBLE ZERO - the exact bug this replaces.
    # Measured: root -> enc 1.021276318 / clients 4; non-root -> enc 0.0 / clients 3.
    # `clients 3` is plausible on its own, so the gauge is NOT a usable canary. Fail loudly.
    sys.exit("must run as root - refusing to publish a fake zero (fdinfo needs euid 0)")

_card, _pdev = discover_card()
CARD     = os.environ.get("AMDGPU_CARD") or _card
PDEV     = os.environ.get("AMDGPU_PDEV") or _pdev
if not CARD or not PDEV:
    # Exit non-zero so OnFailure= fires. Do NOT write a zero - a fake zero is
    # indistinguishable from an idle GPU, which is the bug this script replaces.
    sys.exit("no amdgpu card found under /sys/class/drm - refusing to publish a fake zero")
OUTPUT   = os.environ.get("AMDGPU_OUT",  "/tmp/node_exporter/amdgpu.prom")
STATE    = os.environ.get("AMDGPU_STATE", "/var/lib/amdgpu-engine-metrics/state.json")
# pre-seed so the series exist before the first transcode (else Grafana shows "no data")
ENGINES  = ("gfx", "compute", "enc", "dec")

ENGINE_RE = re.compile(r"^drm-engine-([a-z0-9_]+):\s+(\d+)\s+ns$", re.M)
CLIENT_RE = re.compile(r"^drm-client-id:\s+(\d+)$", re.M)
PDEV_RE   = re.compile(r"^drm-pdev:\s+(\S+)$", re.M)
DRIVER_RE = re.compile(r"^drm-driver:\s+amdgpu$", re.M)


def scan():
    """-> {client_id: {engine: ns}} for amdgpu clients on this pdev.

    Resolves each fd's symlink BEFORE opening its fdinfo. The obvious implementation - open
    and regex-scan every /proc/*/fdinfo/* - reads ~13,000 files to find the ~4 that are DRM
    handles, and measured 605-638 ms of real CPU per run (user+sys ~= wall, so it is compute,
    not I/O wait). Filtering on the symlink target first measured 36-42 ms for byte-identical
    per-engine nanoseconds and identical client ids. At a 15 s cadence that is 0.25 % of a
    core instead of 4.3 %.
    """
    clients = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        fd_dir = f"/proc/{pid}/fd"
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            continue                      # process exited, or not ours to read
        for fd in fds:
            try:
                # cheap: one readlink, no file open. DRM handles point at /dev/dri/*.
                if not os.readlink(f"{fd_dir}/{fd}").startswith("/dev/dri/"):
                    continue
                with open(f"/proc/{pid}/fdinfo/{fd}") as fh:
                    txt = fh.read()
            except OSError:
                continue
            # keep every original filter - the fast path must not widen what counts
            if not DRIVER_RE.search(txt):
                continue
            m = PDEV_RE.search(txt)
            if not m or m.group(1) != PDEV:
                continue
            c = CLIENT_RE.search(txt)
            if not c:
                continue
            eng = {k: int(v) for k, v in ENGINE_RE.findall(txt)}
            if not eng:
                continue
            # same client, several fds: keep the highest value seen per engine
            cur = clients.setdefault(c.group(1), {})
            for k, v in eng.items():
                if v > cur.get(k, -1):
                    cur[k] = v
    return clients


def atomic_write(path, data):
    # Refuse anything that is not a regular file or absent. os.replace() on a device node
    # DESTROYS it - pointing AMDGPU_OUT at /dev/null during testing replaced the device with
    # a regular file and broke every subsequent redirect on the host until mknod restored it.
    # Use AMDGPU_OUT=- for a dry run instead.
    if os.path.exists(path) and not os.path.isfile(path):
        raise SystemExit(f"refusing to replace non-regular file {path!r} - use AMDGPU_OUT=- to test")
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)          # atomic; node_exporter never sees a partial file
    except BaseException:
        os.unlink(tmp)
        raise


def main():
    try:
        with open(STATE) as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        st = {}
    totals = {e: 0 for e in ENGINES}
    totals.update({k: int(v) for k, v in st.get("totals", {}).items()})
    last   = st.get("last", {})

    live = scan()
    for cid, eng in live.items():
        prev = last.get(cid, {})
        for e, ns in eng.items():
            p = prev.get(e, 0)
            # per-client counter reset (client-id reuse) -> count the whole value
            totals[e] = totals.get(e, 0) + (ns - p if ns >= p else ns)
    new_last = {cid: eng for cid, eng in live.items()}

    lines = ["# HELP amdgpu_engine_busy_seconds_total Cumulative amdgpu engine busy time from DRM fdinfo.",
             "# TYPE amdgpu_engine_busy_seconds_total counter"]
    for e in sorted(totals):
        lines.append(f'amdgpu_engine_busy_seconds_total{{card="{CARD}",engine="{e}"}} {totals[e] / 1e9:.9f}')
    lines += ["# HELP amdgpu_drm_clients Live amdgpu DRM clients with engine counters.",
              "# TYPE amdgpu_drm_clients gauge",
              f'amdgpu_drm_clients{{card="{CARD}"}} {len(live)}', ""]
    body = "\n".join(lines)

    atomic_write(STATE, json.dumps({"totals": totals, "last": new_last}))
    if OUTPUT == "-":
        sys.stdout.write(body)
    else:
        atomic_write(OUTPUT, body)


if __name__ == "__main__":
    main()
