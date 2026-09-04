QUALITY_OPTIONS = [
    "Best",
    "2160p",
    "1440p",
    "1080p",
    "720p",
    "480p",
    "360p",
]

MODE_OPTIONS = [
    "video",
    "mp4_only",
    "audio",
]

FORMAT_MAP: dict[str, str] = {
    # bv = video-only (لا combined formats) → يضمن اختيار أعلى bitrate video-only
    # الترتيب: mp4+m4a أولاً (توافق أعلى) ← ثم أي video+audio ← ثم combined fallback
    "best":  "bv[ext=mp4]+ba[ext=m4a]/bv+ba/b",
    "2160p": "bv[height<=2160][ext=mp4]+ba[ext=m4a]/bv[height<=2160]+ba/b[height<=2160]",
    "1440p": "bv[height<=1440][ext=mp4]+ba[ext=m4a]/bv[height<=1440]+ba/b[height<=1440]",
    "1080p": "bv[height<=1080][ext=mp4]+ba[ext=m4a]/bv[height<=1080]+ba/b[height<=1080]",
    "720p":  "bv[height<=720][ext=mp4]+ba[ext=m4a]/bv[height<=720]+ba/b[height<=720]",
    "480p":  "bv[height<=480][ext=mp4]+ba[ext=m4a]/bv[height<=480]+ba/b[height<=480]",
    "360p":  "bv[height<=360][ext=mp4]+ba[ext=m4a]/bv[height<=360]+ba/b[height<=360]",
    "mp3":   "m4a/bestaudio/best",
    "m4a":   "m4a/bestaudio/best",
}

FORMAT_MAP_MP4: dict[str, str] = {
    "best":  "bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
    "2160p": "bv[height<=2160][ext=mp4]+ba[ext=m4a]/b[height<=2160]",
    "1440p": "bv[height<=1440][ext=mp4]+ba[ext=m4a]/b[height<=1440]",
    "1080p": "bv[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]",
    "720p":  "bv[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]",
    "480p":  "bv[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480]",
    "360p":  "bv[height<=360][ext=mp4]+ba[ext=m4a]/b[height<=360]",
}


def build_format_opts(quality: str, mode: str) -> dict:
    opts: dict = {}

    if mode == "audio":
        audio_format = quality.lower()
        if audio_format not in ("mp3", "m4a"):
            audio_format = "mp3"
        opts["format"] = FORMAT_MAP.get(audio_format, "m4a/bestaudio/best")
        opts["postprocessors"] = _audio_postprocessors(audio_format)
        opts["writethumbnail"] = True
        return opts

    q = quality.lower()

    if mode == "mp4_only":
        opts["format"] = FORMAT_MAP_MP4.get(q, FORMAT_MAP_MP4["best"])
    else:
        # وضع video: يفضّل mp4+m4a، fallback لأي صيغة
        opts["format"] = FORMAT_MAP.get(q, FORMAT_MAP["best"])
        opts["merge_output_format"] = "mp4"

    return opts


def _audio_postprocessors(fmt: str) -> list[dict]:
    pps = [
        {"key": "FFmpegMetadata", "add_metadata": True},
        {"key": "EmbedThumbnail"},
    ]
    if fmt == "mp3":
        pps.insert(0, {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        })
    return pps


def get_common_opts(bin_dir: str, config) -> dict:
    import os
    from pathlib import Path

    bin_path = str(Path(bin_dir).resolve())

    # أضف bin/ للـ PATH حتى يلاقي yt-dlp كلاً من node.exe وffmpeg.exe
    current_path = os.environ.get("PATH", "")
    if bin_path not in current_path:
        os.environ["PATH"] = bin_path + os.pathsep + current_path

    opts = {
        "ffmpeg_location": bin_path,
        "concurrent_fragments": config.get("download.concurrent_fragments", 4),
        "retries": config.get("download.retries", 10),
        "fragment_retries": config.get("download.retries", 10),
        "throttledratelimit": 102400,
        "format_sort": ["vcodec:h264,vp9,av01", "res", "br"],
        "ignoreerrors": False,
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}},
    }

    # تفعيل yt-dlp-ejs لحل JavaScript challenges في YouTube
    ext_args = {"youtube-ejs": {}}

    # دمج extractor_args من الإعدادات إن وجدت
    user_ext_args = config.get("advanced.extractor_args", {})
    if isinstance(user_ext_args, dict):
        for k, v in user_ext_args.items():
            if k not in ext_args:
                ext_args[k] = v
            elif isinstance(v, dict):
                ext_args[k].update(v)

    opts["extractor_args"] = ext_args

    return opts
