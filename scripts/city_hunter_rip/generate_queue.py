#!/usr/bin/env python3
"""Generate a HandBrake v1.x queue file from dvd_config.json.

Structure matches the format produced by HandBrake 1.11.1's own queue export
(queue.from.gui.export.json).  Each entry has three top-level keys:
  Job        — encode parameters consumed by HandBrake's scan/encode pipeline
  Title      — source scan metadata (populated from DVD format constants)
  uiSettings — GUI state snapshot required for proper queue display/import
"""

import json
from pathlib import Path

CONFIG = Path(__file__).parent / "dvd_config.json"
OUTPUT = Path("/mnt/MovieAndTvShows/ToFix/handbreakOutput/queue.json")

# ── DVD format constants (PAL 576p, same across all City Hunter discs) ────────
_PAL_FRAMERATE = {"Den": 1080000, "Num": 27000000}
_DVD_GEOMETRY  = {"Height": 576, "PAR": {"Den": 15, "Num": 16}, "Width": 720}
_DVD_COLOR     = {
    "BitDepth": 8, "ChromaLocation": 1, "ChromaSubsampling": "4:2:0",
    "Format": 0, "Matrix": 6, "Primary": 5, "Range": 1, "Transfer": 1,
}
_AC3_TRACK_ATTRS = {
    "AltCommentary": False, "Commentary": False, "Default": False,
    "Normal": False, "Secondary": False, "VisuallyImpaired": False,
}
_AC3_TRACK_BASE = {
    "Attributes": _AC3_TRACK_ATTRS,
    "BitRate": 192000, "ChannelCount": 2, "ChannelLayout": "stereo",
    "Codec": 2048, "CodecName": "ac3", "CodecParam": 86019,
    "Description": "Unknown (AC3, 2.0 ch, 192 kbps)",
    "LFECount": 0, "Language": "Unknown", "LanguageCode": "und",
    "SampleRate": 48000,
}
_VOBSUB_ATTRS = {
    "4By3": False, "Children": False, "ClosedCaption": False,
    "Commentary": False, "Default": False, "Forced": False, "Large": False,
    "Letterbox": False, "Normal": False, "PanScan": False, "Wide": False,
}
_X265_OPTIONS = (
    "strong-intra-smoothing=0:rect=0:aq-mode=1:rd=4:"
    "psy-rd=0.75:psy-rdoq=4.0:rdoq-level=1:rskip=2"
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _vob_path(disc_path: str, title: int) -> str:
    """Return the main VOB file path for a given VIDEO_TS directory + title."""
    return f"{disc_path}/VTS_{title:02d}_1.VOB"


def _vob_name(title: int) -> str:
    """Return the volume label (VOB stem) for a title number."""
    return f"VTS_{title:02d}_1"


# ── Job section ───────────────────────────────────────────────────────────────

def _make_job(seq, source_vob, title, range_start, range_end, dest_full):
    return {
        "Audio": {
            "AudioList": [
                {
                    "Bitrate": 192,
                    "CompressionLevel": -1.0,
                    "DRC": 0.0,
                    "DitherMethod": "auto",
                    "Encoder": "copy:ac3",
                    "Gain": 0.0,
                    "Mixdown": "none",
                    "Name": "Italian",
                    "NormalizeMixLevel": False,
                    "PresetEncoder": "copy:ac3",
                    "Quality": -3.0,
                    "Samplerate": 0,
                    "Track": 0,
                },
                {
                    "Bitrate": 192,
                    "CompressionLevel": -1.0,
                    "DRC": 0.0,
                    "DitherMethod": "auto",
                    "Encoder": "copy:ac3",
                    "Gain": 0.0,
                    "Mixdown": "none",
                    "Name": "Japanese",
                    "NormalizeMixLevel": False,
                    "PresetEncoder": "copy:ac3",
                    "Quality": -3.0,
                    "Samplerate": 0,
                    "Track": 1,
                },
            ],
            "CopyMask": ["copy:ac3"],
            "FallbackEncoder": "fdk_aac",
        },
        "Destination": {
            "AlignAVStart": False,
            "ChapterList": [],
            "ChapterMarkers": False,
            "File": dest_full,
            "InlineParameterSets": False,
            "Mux": "mkv",
            "Options": {
                "IpodAtom": False,
                "Optimize": False,
            },
        },
        "Filters": {
            "FilterList": [
                {
                    "ID": 4,
                    "Settings": {
                        "block-height": "16",
                        "block-thresh": "40",
                        "block-width": "16",
                        "filter-mode": "2",
                        "mode": "3",
                        "motion-thresh": "1",
                        "spatial-metric": "2",
                        "spatial-thresh": "1",
                    },
                },
                {
                    "ID": 6,
                    "Settings": {
                        "mode": "7",
                    },
                },
                {
                    "ID": 11,
                    "Settings": {
                        "mode": 2,
                        "rate": "27000000/1080000",
                    },
                },
                {
                    "ID": 20,
                    "Settings": {
                        "crop-bottom": 0,
                        "crop-left": 2,
                        "crop-right": 0,
                        "crop-top": 4,
                        "height": 572,
                        "width": 718,
                    },
                },
            ],
        },
        "Metadata": {},
        "PAR": {
            "Den": 15,
            "Num": 16,
        },
        "SequenceID": seq,
        "Source": {
            "Angle": 0,
            "HWDecode": 0,
            "KeepDuplicateTitles": False,
            "Path": source_vob,
            "Range": {
                "End": range_end,
                "Start": range_start,
                "Type": "chapter",
            },
            "Title": title,
        },
        "Subtitle": {
            "Search": {
                "Burn": True,
                "Default": False,
                "Enable": True,
                "Forced": True,
            },
            "SubtitleList": [],
        },
        "Video": {
            "AdapterIndex": -1,
            "AsyncDepth": 0,
            "ChromaLocation": 1,
            "ColorInputFormat": 0,
            "ColorMatrix": 6,
            "ColorOutputFormat": 0,
            "ColorPrimaries": 5,
            "ColorRange": 1,
            "ColorTransfer": 1,
            "Encoder": "x265_10bit",
            "HardwareDecode": 0,
            "Level": "auto",
            "MultiPass": False,
            "Options": _X265_OPTIONS,
            "PasshtruHDRDynamicMetadata": 6,
            "Preset": "slow",
            "Profile": "main10",
            "Quality": 20.0,
            "Tune": "",
            "Turbo": False,
        },
    }


# ── Title section (source scan metadata) ─────────────────────────────────────

def _make_title(source_vob, title_num, vol_name):
    return {
        "AngleCount": 1,
        "AudioList": [
            {**_AC3_TRACK_BASE, "TrackNumber": 1},
            {**_AC3_TRACK_BASE, "TrackNumber": 2},
        ],
        "ChapterList": [
            {
                "Duration": {"Hours": 0, "Minutes": 25, "Seconds": 14, "Ticks": 136314111},
                "Name": "Chapter 1",
            }
        ],
        "Color": _DVD_COLOR,
        "Crop": [4, 0, 2, 0],
        "Duration": {"Hours": 0, "Minutes": 25, "Seconds": 14, "Ticks": 136314111},
        "FrameRate": _PAL_FRAMERATE,
        "Geometry": _DVD_GEOMETRY,
        "Index": title_num,
        "InterlaceDetected": False,
        "KeepDuplicateTitles": False,
        "LooseCrop": [0, 0, 2, 0],
        "Metadata": {},
        "Name": vol_name,
        "Path": source_vob,
        "Playlist": -1,
        "SubtitleList": [
            {
                "Attributes": _VOBSUB_ATTRS,
                "Format": "bitmap",
                "Language": "Unknown (VOBSUB)",
                "LanguageCode": "und",
                "Source": 0,
                "SourceName": "VOBSUB",
                "TrackNumber": 1,
            }
        ],
        "Type": 2,
        "VideoCodec": "mpeg2video",
    }


# ── uiSettings section (GUI state snapshot) ───────────────────────────────────

def _make_ui_settings(source_vob, vol_name, title_num, range_start, range_end,
                      dest_full, dest_dir, dest_file):
    return {
        "AlignAVStart": False,
        "AudioAllowAACPass": True,
        "AudioAllowAC3Pass": False,
        "AudioAllowALACPass": False,
        "AudioAllowDTSHDPass": False,
        "AudioAllowDTSPass": False,
        "AudioAllowEAC3Pass": False,
        "AudioAllowFLACPass": False,
        "AudioAllowMP2Pass": False,
        "AudioAllowMP3Pass": False,
        "AudioAllowOPUSPass": False,
        "AudioAllowPCMPass": False,
        "AudioAllowTRUEHDPass": False,
        "AudioAllowVORBISPass": False,
        "AudioAutomaticNamingBehavior": "unnamed",
        "AudioBitrate": "160",
        "AudioCopyMask": ["copy:aac"],
        "AudioEncoder": "fdk_aac",
        "AudioEncoderFallback": "fdk_aac",
        "AudioLanguageList": [],
        "AudioList": [
            {
                "AudioBitrate": 160,
                "AudioCompressionLevel": -1.0,
                "AudioDitherMethod": "auto",
                "AudioEncoder": "fdk_aac",
                "AudioMixdown": "stereo",
                "AudioNormalizeMixLevel": False,
                "AudioSamplerate": "auto",
                "AudioTrackDRCSlider": 0.0,
                "AudioTrackGainSlider": 0.0,
                "AudioTrackQuality": 1.0,
                "AudioTrackQualityEnable": False,
            }
        ],
        "AudioMixdown": "stereo",
        "AudioSamplerate": "auto",
        "AudioSecondaryEncoderMode": True,
        "AudioTrack": "0",
        "AudioTrackBitrateEnable": True,
        "AudioTrackDRCSlider": 0.90000000000000002,
        "AudioTrackDRCValue": "Off",
        "AudioTrackGainSlider": 0.0,
        "AudioTrackGainValue": "0dB",
        "AudioTrackName": "Stereo",
        "AudioTrackNamePassthru": True,
        "AudioTrackQuality": -1.0,
        "AudioTrackQualityEnable": False,
        "AudioTrackQualityValue": "-3",
        "AudioTrackQualityX": 1.0,
        "AudioTrackSelectionBehavior": "first",
        "ChapterMarkers": True,
        "ChildrenArray": [],
        "Default": False,
        "DisplayHeight": 572.0,
        "FileFormat": "av_mkv",
        "Folder": False,
        "FolderOpen": False,
        "ImportFile": None,
        "ImportLanguage": "und",
        "ImportOffset": 0.0,
        "InlineParameterSets": False,
        "MainWhenComplete": "nothing",
        "MetaAlbumArtist": "",
        "MetaArtist": "",
        "MetaComment": "",
        "MetaDescription": "",
        "MetaGenre": "",
        "MetaLongDescription": "",
        "MetaName": "",
        "MetaReleaseDate": "",
        "MetadataPassthru": True,
        "Mp4iPodCompatible": False,
        "Optimize": False,
        "PictureAllowUpscaling": False,
        "PictureAutoCrop": True,
        "PictureBottomCrop": 0.0,
        "PictureChromaSmoothCustom": "",
        "PictureChromaSmoothPreset": "off",
        "PictureChromaSmoothTune": "none",
        "PictureColorspaceCustom": "",
        "PictureColorspacePreset": "off",
        "PictureCombDetectCustom": "",
        "PictureCombDetectPreset": "default",
        "PictureCropMode": 0,
        "PictureDARWidth": 766.0,
        "PictureDeblockCustom": "strength=strong:thresh=20:blocksize=8",
        "PictureDeblockPreset": "off",
        "PictureDeblockTune": "medium",
        "PictureDeinterlaceCustom": "",
        "PictureDeinterlaceDecomb": False,
        "PictureDeinterlaceFilter": "decomb",
        "PictureDeinterlacePreset": "default",
        "PictureDenoiseCustom": "",
        "PictureDenoiseFilter": "off",
        "PictureDenoisePreset": "",
        "PictureDenoiseTune": "none",
        "PictureDetelecine": "off",
        "PictureDetelecineCustom": "",
        "PictureForceHeight": 0,
        "PictureForceWidth": 0,
        "PictureHeight": 576,
        "PictureItuPAR": False,
        "PictureKeepRatio": True,
        "PictureLeftCrop": 2.0,
        "PictureModulus": 2,
        "PicturePAR": "auto",
        "PicturePARHeight": 15.0,
        "PicturePARWidth": 16.0,
        "PicturePadBottom": 0.0,
        "PicturePadColor": "black",
        "PicturePadLeft": 0.0,
        "PicturePadMode": "none",
        "PicturePadRight": 0.0,
        "PicturePadTop": 0.0,
        "PictureRightCrop": 0.0,
        "PictureRotate": "angle=0:hflip=0",
        "PictureSharpenCustom": "",
        "PictureSharpenFilter": "off",
        "PictureSharpenPreset": "",
        "PictureSharpenTune": "",
        "PictureTopCrop": 4.0,
        "PictureUseMaximumSize": True,
        "PictureWidth": 720,
        "Preferences": {
            "ActivityFontFamily": "monospace",
            "ActivityFontSize": 6.0,
            "AddCC": False,
            "AutoScan": True,
            "CustomNotificationMessage": "",
            "CustomTmpDir": None,
            "CustomTmpEnable": False,
            "DiskFreeCheck": True,
            "DiskFreeLimitGB": 10.0,
            "EncodeLogLocation": False,
            "ExcludedFileExtensions": ["jpg", "png", "srt", "ssa", "ass", "txt"],
            "ExportDirectory": "/output",
            "HideAdvancedVideoSettings": True,
            "LimitMaxDuration": False,
            "LogLongevity": "month",
            "LoggingLevel": "1",
            "LowBatteryLevel": 15,
            "MaxTitleDuration": 0.0,
            "MinTitleDuration": 10.0,
            "NativeFileChooser": True,
            "NotifyOnEncodeDone": False,
            "NotifyOnQueueDone": True,
            "PauseEncodingOnBatteryPower": False,
            "PauseEncodingOnLowBattery": False,
            "PauseEncodingOnPowerSave": True,
            "PreferredLanguage": "und",
            "RecursiveFolderScan": False,
            "RemoveFinishedJobs": False,
            "ShowMiniPreview": True,
            "SrtDir": ".",
            "SyncTitleSettings": True,
            "UiLanguage": "",
            "UseM4v": True,
            "VideoQualityGranularity": "1",
            "WhenComplete": "nothing",
            "allow_tweaks": False,
            "auto_name": True,
            "auto_name_template": "{source}",
            "check_updates": "weekly",
            "default_source": source_vob,
            "destination_dir": "/output",
            "hbfd": False,
            "hbfd_feature": False,
            "last_update_check": 0,
            "live_duration": 15.0,
            "preset_window_height": 1,
            "preset_window_width": 1,
            "presets_window_height": 600,
            "presets_window_width": 300,
            "preview_count": 10.0,
            "preview_show_crop": False,
            "preview_x": 254,
            "preview_y": 98,
            "reduce_hd_preview": True,
            "show_queue_sidebar": True,
            "update_skip_version": 0,
            "use_dvdnav": True,
            "version": "0.1",
            "window_height": 1079,
            "window_width": 1920,
        },
        "PreferredLanguage": "und",
        "PresetCategory": "new",
        "PresetDescription": "H.265 video (up to 576p25) and AAC stereo audio, in an MKV container.",
        "PresetDisabled": False,
        "PresetFullName": "/Matroska/H.265 MKV 576p25",
        "PresetName": "H.265 MKV 576p25",
        "PtoPType": "chapter",
        "QueueWhenComplete": "nothing",
        "SrtCodeset": "ISO-8859-1",
        "SubtitleAddCC": False,
        "SubtitleAddForeignAudioSearch": True,
        "SubtitleAddForeignAudioSubtitle": False,
        "SubtitleBurnBDSub": True,
        "SubtitleBurnBehavior": "foreign",
        "SubtitleBurnDVDSub": True,
        "SubtitleBurned": True,
        "SubtitleDefaultTrack": False,
        "SubtitleForced": True,
        "SubtitleImportDisable": True,
        "SubtitleLanguageList": [],
        "SubtitleTrack": "0",
        "SubtitleTrackName": "",
        "SubtitleTrackNamePassthru": True,
        "SubtitleTrackSelectionBehavior": "none",
        "Type": 0,
        "UsesPictureFilters": True,
        "VideoAvgBitrate": 1200.0,
        "VideoColorMatrixCodeOverride": 0,
        "VideoColorRange": "limited",
        "VideoEncoder": "x265_10bit",
        "VideoFramerate": "25",
        "VideoFramerateCFR": False,
        "VideoFramerateMode": "pfr",
        "VideoFrameratePFR": True,
        "VideoFramerateVFR": False,
        "VideoGrayScale": False,
        "VideoHWDecode": 0,
        "VideoLevel": "auto",
        "VideoMultiPass": True,
        "VideoOptionExtra": _X265_OPTIONS,
        "VideoPasshtruHDRDynamicMetadata": "all",
        "VideoPreset": "slow",
        "VideoPresetSlider": 6.0,
        "VideoProfile": "main10",
        "VideoQualitySlider": 20,
        "VideoQualityType": 2,
        "VideoScaler": "swscale",
        "VideoTune": "none",
        "VideoTurboMultiPass": False,
        "activity_location": "/config/.ghb/Activity.log.1075",
        "angle": 1.0,
        "angle_count": 1,
        "chapter_list": [],
        "crop_mode": "auto",
        "dest_dir": dest_dir,
        "dest_file": dest_file,
        "destination": dest_full,
        "end_point": float(range_end),
        "final_aspect_ratio": "4.017:3",
        "final_storage_size": "718 x 572",
        "hflip": False,
        "job_status": 0,
        "job_unique_id": 0,
        "preset_modified": False,
        "preset_reload": False,
        "preview_frame": 2,
        "queue_activity_location": "",
        "resolution_limit": "576p",
        "rotate": "0",
        "scale_height": 572.0,
        "scale_width": 718.0,
        "single_title": title_num,
        "source": source_vob,
        "source_aspect_ratio": "4:3",
        "source_display_size": "768 x 576",
        "source_height": 576,
        "source_label": vol_name,
        "source_storage_size": "720 x 576",
        "source_width": 720,
        "start_frame": -1,
        "start_point": float(range_start),
        "title": str(title_num),
        "title_selected": False,
        "volume": vol_name,
        "vquality_type_bitrate": False,
        "vquality_type_constant": True,
        "x264FastDecode": False,
        "x264Option": "",
        "x264UseAdvancedOptions": False,
        "x264ZeroLatency": False,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def make_entry(seq, disc_path, title, range_start, range_end, season, episode, plex_title):
    source_vob = _vob_path(disc_path, title)
    vol_name   = _vob_name(title)
    dest_dir   = f"/output/City Hunter/Season {season:02d}"
    dest_file  = f"{plex_title} - S{season:02d}E{episode:02d}.mkv"
    dest_full  = f"{dest_dir}/{dest_file}"

    return {
        "Job":        _make_job(seq, source_vob, title, range_start, range_end, dest_full),
        "Title":      _make_title(source_vob, title, vol_name),
        "uiSettings": _make_ui_settings(
            source_vob, vol_name, title, range_start, range_end,
            dest_full, dest_dir, dest_file,
        ),
    }


def main():
    cfg = json.loads(CONFIG.read_text())
    plex_title = cfg["plex_title"]
    entries = []
    season_counts = {}

    for s in cfg["seasons"]:
        sn  = s["season"]
        cpe = s["chapters_per_episode"]
        title = s["title"]
        season_counts[sn] = 0

        for disc in s["discs"]:
            for i, ep in enumerate(disc["episodes"]):
                r_start = i * cpe + 1
                r_end   = r_start + cpe - 1
                entries.append(make_entry(
                    len(entries), disc["path"], title,
                    r_start, r_end, sn, ep, plex_title,
                ))
                season_counts[sn] += 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(entries, indent=4))

    print(f"Total jobs: {len(entries)}")
    for sn, count in sorted(season_counts.items()):
        print(f"  Season {sn:02d}: {count} episodes")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
