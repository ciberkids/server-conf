#!/usr/bin/env python3
"""
Yattaman MKV → individual episodes splitter.

Each of the 16 source MKVs contains 6–7 episodes with embedded chapter markers.
Every 5 chapters = 1 episode (opening + part-A + part-B + eyecatch + ED/preview).
The final episode of the series (ep 108) has 4 chapters — handled automatically.

Split is lossless: ffmpeg -c copy, no re-encoding, no quality loss.
Original files are never touched.

Output: /mnt/MovieAndTvShows/ToFix/Yattaman (1977)/Season 01/
        Yattaman (1977) - S01E01.mkv … Yattaman (1977) - S01E108.mkv
        (Move to TvShows when complete — same filesystem, instant rename)

Usage:
  python3 split_episodes.py              # split everything
  python3 split_episodes.py --dry-run    # print plan, don't run
  python3 split_episodes.py --from=E050  # resume from episode 50
  python3 split_episodes.py --from=E001 --to=E001  # test single episode
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
SOURCE_DIR  = Path("/mnt/MovieAndTvShows/ToFix/Yattaman")
OUTPUT_DIR  = Path("/mnt/MovieAndTvShows/ToFix/Yattaman (1977)/Season 01")
SHOW_TITLE  = "Yattaman (1977)"

CHAPTERS_PER_EP = 5   # every 5 chapters = 1 episode


def get_chapters(mkv: Path) -> list[dict]:
    """Return list of chapter dicts from ffprobe."""
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_chapters", "-print_format", "json", str(mkv)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(r.stdout).get("chapters", [])


def natural_sort_key(p: Path) -> int:
    """Sort 'YATTAMAN 2_...' numerically by the volume number."""
    m = re.search(r"YATTAMAN\s+(\d+)", p.name, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def build_jobs(source_dir: Path) -> list[dict]:
    """Return a flat list of split jobs in episode order."""
    files = sorted(source_dir.glob("*.mkv"), key=natural_sort_key)
    jobs = []
    ep_num = 1

    for mkv in files:
        chapters = get_chapters(mkv)
        n = len(chapters)

        # Group into sets of CHAPTERS_PER_EP; remainder becomes the last episode
        groups = []
        i = 0
        while i < n:
            end = min(i + CHAPTERS_PER_EP, n)
            groups.append(chapters[i:end])
            i = end

        for group in groups:
            start = float(group[0]["start_time"])
            end   = float(group[-1]["end_time"])
            out   = OUTPUT_DIR / f"{SHOW_TITLE} - S01E{ep_num:03d}.mkv"
            jobs.append({
                "ep":    ep_num,
                "src":   mkv,
                "start": start,
                "end":   end,
                "out":   out,
                "n_ch":  len(group),
            })
            ep_num += 1

    return jobs


def split(job: dict) -> int:
    """Run ffmpeg to extract one episode. Returns exit code."""
    cmd = [
        "ffmpeg", "-hide_banner",
        "-ss",  str(job["start"]),
        "-to",  str(job["end"]),
        "-i",   str(job["src"]),
        "-map", "0",            # copy ALL streams (video, all audio, all subtitles)
        "-c",   "copy",
        "-map_chapters", "-1",  # drop source chapter list (wrong for a single episode)
        "-avoid_negative_ts", "make_zero",
        "-y",   str(job["out"]),
    ]
    return subprocess.run(cmd).returncode


def main() -> None:
    args = sys.argv[1:]
    dry_run  = "--dry-run" in args
    from_ep  = next((int(a.split("=", 1)[1].lstrip("Ee")) for a in args if a.startswith("--from=")), 1)
    to_ep    = next((int(a.split("=", 1)[1].lstrip("Ee")) for a in args if a.startswith("--to=")), None)

    jobs = build_jobs(SOURCE_DIR)

    # ── Dry-run: print plan ───────────────────────────────────────────────────
    if dry_run:
        print(f"[split] {len(jobs)} episodes from {len(set(j['src'] for j in jobs))} source files\n")
        current_src = None
        for j in jobs:
            if j["src"] != current_src:
                current_src = j["src"]
                print(f"  {current_src.name}")
            m, s = divmod(j["start"], 60)
            em, es = divmod(j["end"], 60)
            print(f"    E{j['ep']:03d}  {int(m):02d}:{int(s):02d}→{int(em):02d}:{int(es):02d}"
                  f"  ({j['n_ch']} chapters)  →  {j['out'].name}")
        return

    # ── Real run ──────────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pending = [j for j in jobs if j["ep"] >= from_ep and (to_ep is None or j["ep"] <= to_ep)]
    print(f"[split] {len(pending)} episode(s) to extract"
          f"  (starting from E{from_ep:03d})\n")

    for j in pending:
        out = j["out"]
        if out.exists():
            print(f"  E{j['ep']:03d}  SKIP (already exists)  {out.name}")
            continue

        print(f"  E{j['ep']:03d}  {j['src'].name}  "
              f"{j['start']:.1f}s → {j['end']:.1f}s  ({j['n_ch']} ch)")

        rc = split(j)
        if rc != 0:
            print(f"[split] ERROR: E{j['ep']:03d} failed (exit {rc})", file=sys.stderr)
            sys.exit(rc)

    print("\n[split] Done.")


if __name__ == "__main__":
    main()
