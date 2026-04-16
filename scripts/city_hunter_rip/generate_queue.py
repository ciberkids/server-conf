#!/usr/bin/env python3
"""Generate a HandBrake v1.x queue file from dvd_config.json."""

import json
from pathlib import Path

CONFIG = Path(__file__).parent / "dvd_config.json"
OUTPUT = Path("/mnt/MovieAndTvShows/ToFix/handbreakOutput/queue.json")


def make_job(seq, source_path, title, range_start, range_end, season, episode, plex_title):
    return {
        "Job": {
            "Sequence": seq,
            "Source": {
                "Path": source_path,
                "Title": title,
                "Range": {"Type": "chapter", "Start": range_start, "End": range_end},
            },
            "Destination": {
                "File": f"/output/City Hunter/Season {season:02d}/{plex_title} - S{season:02d}E{episode:02d}.mkv",
                "Format": "av_mkv",
                "AlignAVStart": False,
                "InlineParameterSets": False,
                "ChapterMarkers": True,
                "Options": {},
            },
            "Video": {
                "Encoder": "x265_10bit",
                "FramerateMode": "pfr",
                "Framerate": 0,
                "Quality": 20.0,
                "QualityType": 2,
                "Preset": "slow",
                "Profile": "main10",
                "Level": "auto",
                "Tune": "",
                "Options": "strong-intra-smoothing=0:rect=0:aq-mode=1:rd=4:psy-rd=0.75:psy-rdoq=4.0:rdoq-level=1:rskip=2",
                "MultiPass": False,
                "Turbo": False,
                "ColorMatrixCode": 0,
            },
            "Audio": {
                "CopyMask": ["copy:ac3"],
                "FallbackEncoder": "fdk_aac",
                "AudioList": [
                    {"Track": 0, "Encoder": "copy:ac3", "Mixdown": "none",
                     "Samplerate": 0, "Gain": 0, "DRC": 0.0, "Name": "Italian"},
                    {"Track": 1, "Encoder": "copy:ac3", "Mixdown": "none",
                     "Samplerate": 0, "Gain": 0, "DRC": 0.0, "Name": "Japanese"},
                ]
            },
            "Subtitle": {"SubtitleList": [], "PassthroughFlags": 0},
            "Filters": {
                "FilterList": [{"ID": 7, "Preset": "default", "Settings": {}}]
            },
            "Metadata": {},
        }
    }


def main():
    cfg = json.loads(CONFIG.read_text())
    plex_title = cfg["plex_title"]
    jobs = []
    season_counts = {}

    for s in cfg["seasons"]:
        sn = s["season"]
        cpe = s["chapters_per_episode"]
        title = s["title"]
        season_counts[sn] = 0

        for disc in s["discs"]:
            for i, ep in enumerate(disc["episodes"]):
                r_start = i * cpe + 1
                r_end = r_start + cpe - 1
                jobs.append(make_job(len(jobs), disc["path"], title,
                                     r_start, r_end, sn, ep, plex_title))
                season_counts[sn] += 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(jobs, indent=2))

    print(f"Total jobs: {len(jobs)}")
    for sn, count in sorted(season_counts.items()):
        print(f"  Season {sn}: {count} episodes")
    print(f"Output written to: {OUTPUT}")


if __name__ == "__main__":
    main()
