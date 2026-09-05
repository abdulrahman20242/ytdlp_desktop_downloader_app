from pathlib import Path
from yt_dlp import YoutubeDL

BIN_DIR = Path("bin")


def extract_info(url: str) -> dict | None:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": str(BIN_DIR.resolve()),
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return ydl.sanitize_info(info)
    except Exception:
        return None


def get_available_qualities(url: str) -> list[str]:
    """Return 'Best' plus preset tiers at or below the video's max height.

    Each tier is a height *threshold*, not an exact resolution: a 1080p video
    yields Best, 1080p, 720p, ... and never 1440p/2160p, because no format
    reaches those heights.
    """
    info = extract_info(url)
    if not info:
        return ["Best"]

    heights: set[int] = set()
    for fmt in info.get("formats", []):
        h = fmt.get("height")
        if h:
            heights.add(h)

    thresholds = [2160, 1440, 1080, 720, 480, 360, 240]
    return ["Best"] + [f"{h}p" for h in thresholds if any(x >= h for x in heights)]


def extract_thumbnail(info: dict) -> str | None:
    return info.get("thumbnail") or None


def extract_title(info: dict) -> str:
    return info.get("title") or ""


def extract_duration(info: dict) -> int:
    return info.get("duration") or 0


def extract_uploader(info: dict) -> str:
    return info.get("uploader") or ""
