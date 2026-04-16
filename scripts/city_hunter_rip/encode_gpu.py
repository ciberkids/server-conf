#!/usr/bin/env python3
"""
City Hunter DVD → MKV encoder using ffmpeg + VA-API (hevc_vaapi).

Reads disc layout from dvd_config.json and encodes all episodes directly
on the Optimus Prime host — no HandBrake GUI or queue file needed.

Requirements (host, already satisfied on Optimus Prime):
  - ffmpeg with dvdvideo demuxer + hevc_vaapi encoder
  - /dev/dri/renderD128 (AMD GPU, VA-API)

Usage:
  python3 encode_gpu.py               # encode all 140 episodes
  python3 encode_gpu.py --dry-run     # print ffmpeg commands, don't run
  python3 encode_gpu.py --from=S02E05 # resume from a specific episode
  python3 encode_gpu.py --season=1    # encode only season 1

Output: /mnt/MovieAndTvShows/ToFix/handbreakOutput/City Hunter (1987)/Season XX/
"""

import json
import subprocess
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "dvd_config.json"

# dvd_config.json stores /data/... paths (HandBrake container mount).
# On the host those map to /mnt/MovieAndTvShows/ToFix/...
CONTAINER_PREFIX = "/data"
HOST_PREFIX      = Path("/mnt/MovieAndTvShows/ToFix")

OUTPUT_BASE   = Path("/mnt/MovieAndTvShows/ToFix/handbreakOutput")
VAAPI_DEVICE  = "/dev/dri/renderD128"

# ── Encoding settings ──────────────────────────────────────────────────────────
# Crop: HandBrake auto-detected top=4, left=2 on disc 1; same across all discs.
# Format: w:h:x:y  (x=left offset, y=top offset)
CROP = "718:572:2:4"

# Constant QP for hevc_vaapi.  24 gives excellent quality at 576p; lower = better.
QP = 24


def container_to_host(path: str) -> Path:
    """Convert a /data/... path from dvd_config.json to the host filesystem."""
    rel = path.removeprefix(CONTAINER_PREFIX).lstrip("/")
    return HOST_PREFIX / rel


def disc_root(disc_path: str) -> str:
    """Strip /VIDEO_TS suffix — ffmpeg's dvdvideo demuxer needs the disc root."""
    return container_to_host(disc_path).as_posix().removesuffix("/VIDEO_TS")


def build_ffmpeg_cmd(
    disc: str,
    title: int,
    chapter_start: int,
    chapter_end: int,
    output: Path,
) -> list[str]:
    return [
        "ffmpeg", "-hide_banner",
        # VA-API device
        "-vaapi_device", VAAPI_DEVICE,
        # DVD demuxer: IFO-aware, native chapter selection
        # -preindex does a 2-pass pre-scan for accurate chapter boundary timestamps
        "-f", "dvdvideo",
        "-title", str(title),
        "-chapter_start", str(chapter_start),
        "-chapter_end", str(chapter_end),
        "-preindex", "1",
        "-i", disc,
        # Stream mapping: video + both audio tracks + first subtitle (VOBSUB)
        "-map", "0:v:0",
        "-map", "0:a:0",        # Italian AC3
        "-map", "0:a:1",        # Japanese AC3
        "-map", "0:s:0",        # Italian VOBSUB (forced subs for on-screen text)
        # Video filter chain: crop on CPU → upload to GPU → motion-adaptive deinterlace
        # SAR (16:15) is preserved automatically from the mpeg2video stream
        "-vf", f"crop={CROP},format=nv12,hwupload,deinterlace_vaapi=mode=motion_adaptive:rate=frame",
        # Video encoder: HEVC Main via VA-API at constant QP
        "-c:v", "hevc_vaapi",
        "-qp", str(QP),
        # Audio: passthrough (AC3 192 kbps, no re-encode)
        "-c:a", "copy",
        "-metadata:s:a:0", "title=Italian",
        "-metadata:s:a:1", "title=Japanese",
        # Subtitle: copy VOBSUB track into MKV
        "-c:s", "copy",
        # Overwrite without asking
        "-y",
        str(output),
    ]


def main() -> None:
    args = sys.argv[1:]
    dry_run    = "--dry-run" in args
    from_ep    = next((a.split("=", 1)[1].upper() for a in args if a.startswith("--from=")), None)
    only_season = next((int(a.split("=", 1)[1]) for a in args if a.startswith("--season=")), None)

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    series_title = config["plex_title"]  # "City Hunter (1987)"

    # Build the full job list
    jobs: list[dict] = []
    for season in config["seasons"]:
        s = season["season"]
        if only_season is not None and s != only_season:
            continue

        title             = season["title"]
        chapters_per_ep   = season["chapters_per_episode"]

        for disc_info in season["discs"]:
            root = disc_root(disc_info["path"])

            for i, ep_num in enumerate(disc_info["episodes"]):
                ch_start = i * chapters_per_ep + 1
                ch_end   = ch_start + chapters_per_ep - 1
                ep_id    = f"S{s:02d}E{ep_num:02d}"

                out_dir  = OUTPUT_BASE / series_title / f"Season {s:02d}"
                out_file = out_dir / f"{series_title} - {ep_id}.mkv"

                jobs.append({
                    "ep_id":   ep_id,
                    "disc":    root,
                    "title":   title,
                    "ch_start": ch_start,
                    "ch_end":   ch_end,
                    "out_dir":  out_dir,
                    "out_file": out_file,
                })

    # --from= resume: skip everything before the specified episode ID
    if from_ep:
        idx = next((i for i, j in enumerate(jobs) if j["ep_id"] == from_ep), None)
        if idx is None:
            print(f"[encode] ERROR: episode {from_ep} not found in config", file=sys.stderr)
            sys.exit(1)
        jobs = jobs[idx:]

    print(f"[encode] {len(jobs)} episode(s) to encode  (QP={QP}, VA-API {VAAPI_DEVICE})")

    for n, job in enumerate(jobs, 1):
        out_dir  = job["out_dir"]
        out_file = job["out_file"]
        ep_id    = job["ep_id"]

        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = build_ffmpeg_cmd(
            disc=job["disc"],
            title=job["title"],
            chapter_start=job["ch_start"],
            chapter_end=job["ch_end"],
            output=out_file,
        )

        print(f"\n[{n}/{len(jobs)}] {ep_id}  chapters {job['ch_start']}–{job['ch_end']}  →  {out_file.name}")
        if dry_run:
            print("  " + " ".join(cmd))
            continue

        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"[encode] ERROR: {ep_id} failed (exit {result.returncode})", file=sys.stderr)
            sys.exit(result.returncode)

    print("\n[encode] Done.")


if __name__ == "__main__":
    main()
