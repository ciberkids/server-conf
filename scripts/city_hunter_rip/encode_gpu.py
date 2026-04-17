#!/usr/bin/env python3
"""
City Hunter DVD → MKV encoder using ffmpeg + VA-API (hevc_vaapi).

Reads disc layout from dvd_config.json and encodes all episodes directly
on the Optimus Prime host — no HandBrake GUI or queue file needed.

Pipeline (two-process pipe):
  [ffmpeg #1] DVD → bwdif (CPU deinterlace) → crop → rawvideo yuv420p → stdout
         ↓ pipe
  [ffmpeg #2] stdin rawvideo → hwupload → hevc_vaapi → video-only temp MKV
  [ffmpeg #3] DVD → audio + subtitles copy → audio temp MKV  (fast, no re-encode)
  [ffmpeg #4] video temp + audio temp → mux → final MKV

The two-process pipe is required because the dvdvideo demuxer signals a flush at
every internal VOB cell boundary (not just chapter boundaries), which causes
hwupload to attempt a filter reinit.  That reinit fails with ENOSYS on AMD VA-API.
Piping rawvideo between two ffmpeg processes hides all cell-boundary signals from
the GPU encoder, which sees only a clean continuous yuv420p stream.

Requirements (host, already satisfied on Optimus Prime):
  - ffmpeg with dvdvideo demuxer + hevc_vaapi encoder
  - /dev/dri/renderD128 (AMD GPU, VA-API)

Usage:
  python3 encode_gpu.py               # encode all 140 episodes
  python3 encode_gpu.py --dry-run     # print pipeline stages, don't run
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
CROP        = "718:572:2:4"
VIDEO_SIZE  = "718x572"        # result of the crop, used by the encoder side
FRAMERATE   = "25"             # PAL DVD

# Constant QP for hevc_vaapi.  22 gives very good quality at 576p; lower = better.
QP = 22


def container_to_host(path: str) -> Path:
    """Convert a /data/... path from dvd_config.json to the host filesystem."""
    rel = path.removeprefix(CONTAINER_PREFIX).lstrip("/")
    return HOST_PREFIX / rel


def disc_root(disc_path: str) -> str:
    """Strip /VIDEO_TS suffix — ffmpeg's dvdvideo demuxer needs the disc root."""
    return container_to_host(disc_path).as_posix().removesuffix("/VIDEO_TS")


def dvd_input_args(disc: str, title: int, ch_start: int, ch_end: int) -> list[str]:
    return [
        "-f", "dvdvideo",
        "-title", str(title),
        "-chapter_start", str(ch_start),
        "-chapter_end", str(ch_end),
        "-preindex", "1",
        "-i", disc,
    ]


def encode_episode(disc: str, title: int, ch_start: int, ch_end: int, output: Path) -> int:
    """
    Encode one episode using the two-process pipe pipeline.
    Returns ffmpeg exit code (0 = success).
    """
    video_tmp = output.with_suffix(".video.tmp.mkv")
    audio_tmp = output.with_suffix(".audio.tmp.mkv")

    try:
        # ── Stage 1: decode video → pipe → GPU encode ─────────────────────────
        # ffmpeg #1: DVD → bwdif → crop → rawvideo yuv420p → stdout
        decode_cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            *dvd_input_args(disc, title, ch_start, ch_end),
            "-map", "0:v:0",
            "-vf", f"bwdif=mode=send_frame:parity=tff,crop={CROP}",
            "-c:v", "rawvideo", "-pix_fmt", "yuv420p",
            "-f", "rawvideo", "pipe:1",
        ]
        # ffmpeg #2: stdin rawvideo → hwupload → hevc_vaapi → video-only MKV
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
        p1.stdout.close()  # allow p1 to receive SIGPIPE if p2 exits
        p2.wait()
        p1.wait()
        if p2.returncode != 0 or p1.returncode != 0:
            return p2.returncode or p1.returncode

        # ── Stage 2: extract audio + subtitles (copy, no re-encode) ───────────
        audio_cmd = [
            "ffmpeg", "-hide_banner",
            *dvd_input_args(disc, title, ch_start, ch_end),
            "-map", "0:a:0", "-map", "0:a:1", "-map", "0:s:0",
            "-c:a", "copy", "-c:s", "copy",
            "-vn",
            "-f", "matroska", "-y", str(audio_tmp),
        ]
        r = subprocess.run(audio_cmd)
        if r.returncode != 0:
            return r.returncode

        # ── Stage 3: mux video + audio + subtitles ────────────────────────────
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
    dry_run     = "--dry-run" in args
    from_ep     = next((a.split("=", 1)[1].upper() for a in args if a.startswith("--from=")), None)
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

        title           = season["title"]
        chapters_per_ep = season["chapters_per_episode"]

        for disc_info in season["discs"]:
            root = disc_root(disc_info["path"])

            for i, ep_num in enumerate(disc_info["episodes"]):
                ch_start = i * chapters_per_ep + 1
                ch_end   = ch_start + chapters_per_ep - 1
                ep_id    = f"S{s:02d}E{ep_num:02d}"

                out_dir  = OUTPUT_BASE / series_title / f"Season {s:02d}"
                out_file = out_dir / f"{series_title} - {ep_id}.mkv"

                jobs.append({
                    "ep_id":    ep_id,
                    "disc":     root,
                    "title":    title,
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

        print(f"\n[{n}/{len(jobs)}] {ep_id}  chapters {job['ch_start']}–{job['ch_end']}  →  {out_file.name}")

        if dry_run:
            print("  [decode ] ffmpeg -f dvdvideo ... -c:v rawvideo -f rawvideo pipe:1")
            print("  [encode ] ffmpeg -vaapi_device ... -f rawvideo pipe:0 -c:v hevc_vaapi")
            print("  [audio  ] ffmpeg -f dvdvideo ... -c:a copy -c:s copy audio.tmp.mkv")
            print("  [mux    ] ffmpeg -i video.tmp.mkv -i audio.tmp.mkv -c copy output.mkv")
            continue

        rc = encode_episode(
            disc=job["disc"],
            title=job["title"],
            ch_start=job["ch_start"],
            ch_end=job["ch_end"],
            output=out_file,
        )
        if rc != 0:
            print(f"[encode] ERROR: {ep_id} failed (exit {rc})", file=sys.stderr)
            sys.exit(rc)

    print("\n[encode] Done.")


if __name__ == "__main__":
    main()
