#!/usr/bin/env python3
"""
Ghost in the Shell: SAC 2nd GIG DVD → MKV encoder using ffmpeg + VA-API (hevc_vaapi).

Reads disc layout from dvd_config.json.  Each DVD title = 1 episode (title 1 is
always an empty padding entry; episode titles start at 2).

Pipeline (two-process pipe — same as City Hunter):
  [ffmpeg #1] DVD → bwdif (deinterlace/passthrough) → rawvideo yuv420p → stdout
         ↓ pipe
  [ffmpeg #2] stdin rawvideo → hwupload → hevc_vaapi → video-only temp MKV
  [ffmpeg #3] DVD → ITA 5.1 + JPN 5.1 + ITA subtitle (copy) → audio temp MKV
  [ffmpeg #4] video temp + audio temp → mux → final MKV

The two-process pipe is required to hide VOB cell-boundary flush signals from the
AMD VA-API GPU encoder (same ENOSYS issue as City Hunter).

DVDs 1-2 are progressive; DVDs 3-6 are TFF interlaced.  bwdif=mode=send_frame
handles both correctly: passthrough for progressive, proper deinterlace for TFF.

Streams kept per episode:
  a:0  Italian 5.1 AC3 448 kb/s
  a:2  Japanese 5.1 AC3 448 kb/s   (a:1 ITA stereo is dropped)
  s:0  Italian subtitle (Widescreen)

Requirements (Optimus Prime, already satisfied):
  - ffmpeg with dvdvideo demuxer + hevc_vaapi encoder
  - /dev/dri/renderD128 (AMD GPU, VA-API)

Usage:
  python3 encode_gpu.py               # encode all 26 episodes
  python3 encode_gpu.py --dry-run     # print plan, don't run
  python3 encode_gpu.py --from=S02E05 # resume from a specific episode

Output: /mnt/MovieAndTvShows/ToFix/handbreakOutput/
        Ghost in the Shell Stand Alone Complex/Season 02/
"""

import json
import subprocess
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "dvd_config.json"
OUTPUT_BASE = Path("/mnt/MovieAndTvShows/ToFix/handbreakOutput")
VAAPI_DEVICE = "/dev/dri/renderD128"

# ── Encoding settings ──────────────────────────────────────────────────────────
# No crop: per-disc crop values vary too much (x offset 0–10px across discs).
# HEVC compresses black borders near-losslessly.  SAR 64:45 is preserved.
VIDEO_SIZE = "720x576"   # full PAL frame, no crop
FRAMERATE  = "25"        # PAL DVD

# Constant QP for hevc_vaapi.  22 gives very good quality at 576p.
QP = 22

# Episode titles start at 2 on every disc (title 1 is always empty padding).
FIRST_EPISODE_TITLE = 2


def dvd_input_args(disc_path: str, title: int) -> list[str]:
    return [
        "-f", "dvdvideo",
        "-title", str(title),
        "-preindex", "1",
        "-i", disc_path,
    ]


def encode_episode(disc_path: str, title: int, output: Path) -> int:
    """
    Encode one episode from a DVD title.  Returns ffmpeg exit code (0 = success).
    """
    video_tmp = output.with_suffix(".video.tmp.mkv")
    audio_tmp = output.with_suffix(".audio.tmp.mkv")

    try:
        # ── Stage 1: decode video → pipe → GPU encode ─────────────────────────
        decode_cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            *dvd_input_args(disc_path, title),
            "-map", "0:v:0",
            "-vf", "bwdif=mode=send_frame:parity=tff",
            "-c:v", "rawvideo", "-pix_fmt", "yuv420p",
            "-f", "rawvideo", "pipe:1",
        ]
        encode_cmd = [
            "ffmpeg", "-hide_banner",
            "-vaapi_device", VAAPI_DEVICE,
            "-f", "rawvideo", "-pix_fmt", "yuv420p",
            "-video_size", VIDEO_SIZE, "-framerate", FRAMERATE,
            "-i", "pipe:0",
            "-vf", "format=nv12,hwupload",
            "-c:v", "hevc_vaapi", "-qp", str(QP),
            "-f", "matroska", "-y", str(video_tmp),
        ]

        p1 = subprocess.Popen(decode_cmd, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(encode_cmd, stdin=p1.stdout)
        p1.stdout.close()
        p2.wait()
        p1.wait()
        if p2.returncode != 0 or p1.returncode != 0:
            return p2.returncode or p1.returncode

        # ── Stage 2: extract audio + subtitle (copy, no re-encode) ────────────
        audio_cmd = [
            "ffmpeg", "-hide_banner",
            *dvd_input_args(disc_path, title),
            "-map", "0:a:0",   # Italian 5.1
            "-map", "0:a:2",   # Japanese 5.1  (skip a:1 = ITA stereo)
            "-map", "0:s:0",   # Italian subtitle (Widescreen)
            "-c:a", "copy", "-c:s", "copy",
            "-vn",
            "-f", "matroska", "-y", str(audio_tmp),
        ]
        r = subprocess.run(audio_cmd)
        if r.returncode != 0:
            return r.returncode

        # ── Stage 3: mux video + audio + subtitle ─────────────────────────────
        mux_cmd = [
            "ffmpeg", "-hide_banner",
            "-i", str(video_tmp), "-i", str(audio_tmp),
            "-map", "0:v:0",
            "-map", "1:a:0", "-map", "1:a:1", "-map", "1:s:0",
            "-c", "copy",
            "-metadata:s:a:0", "title=Italian",
            "-metadata:s:a:1", "title=Japanese",
            "-f", "matroska", "-y", str(output),
        ]
        r = subprocess.run(mux_cmd)
        return r.returncode

    finally:
        video_tmp.unlink(missing_ok=True)
        audio_tmp.unlink(missing_ok=True)


def main() -> None:
    args = sys.argv[1:]
    dry_run  = "--dry-run" in args
    from_ep  = next((a.split("=", 1)[1].upper() for a in args if a.startswith("--from=")), None)

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    series_title = config["plex_title"]
    season       = config["season"]
    out_dir      = OUTPUT_BASE / series_title / f"Season {season:02d}"

    # Build flat job list
    jobs: list[dict] = []
    for disc_info in config["discs"]:
        disc_path = disc_info["path"]
        for i, ep_num in enumerate(disc_info["episodes"]):
            title  = FIRST_EPISODE_TITLE + i
            ep_id  = f"S{season:02d}E{ep_num:02d}"
            out_file = out_dir / f"{series_title} - {ep_id}.mkv"
            jobs.append({
                "ep_id":     ep_id,
                "disc":      disc_info["disc"],
                "disc_path": disc_path,
                "title":     title,
                "out_file":  out_file,
            })

    # --from= resume
    if from_ep:
        idx = next((i for i, j in enumerate(jobs) if j["ep_id"] == from_ep), None)
        if idx is None:
            print(f"[encode] ERROR: episode {from_ep} not found", file=sys.stderr)
            sys.exit(1)
        jobs = jobs[idx:]

    print(f"[encode] {len(jobs)} episode(s) to encode  (QP={QP}, VA-API {VAAPI_DEVICE})")
    print(f"[encode] Output → {out_dir}\n")

    for n, job in enumerate(jobs, 1):
        ep_id    = job["ep_id"]
        out_file = job["out_file"]

        print(f"[{n}/{len(jobs)}] {ep_id}  disc {job['disc']} title {job['title']}  →  {out_file.name}")

        if dry_run:
            print("  [decode ] ffmpeg -f dvdvideo ... -vf bwdif -c:v rawvideo pipe:1")
            print("  [encode ] ffmpeg -vaapi_device ... -f rawvideo pipe:0 -c:v hevc_vaapi")
            print("  [audio  ] ffmpeg -f dvdvideo ... -map a:0 -map a:2 -map s:0 audio.tmp.mkv")
            print("  [mux    ] ffmpeg -i video.tmp.mkv -i audio.tmp.mkv -c copy output.mkv")
            continue

        if out_file.exists():
            print(f"  SKIP (already exists)")
            continue

        out_dir.mkdir(parents=True, exist_ok=True)

        rc = encode_episode(
            disc_path=job["disc_path"],
            title=job["title"],
            output=out_file,
        )
        if rc != 0:
            print(f"[encode] ERROR: {ep_id} failed (exit {rc})", file=sys.stderr)
            sys.exit(rc)

    print("\n[encode] Done.")


if __name__ == "__main__":
    main()
