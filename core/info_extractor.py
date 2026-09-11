from yt_dlp import YoutubeDL

from utils.paths import bin_dir

BIN_DIR = bin_dir()

_QUALITY_THRESHOLDS = (2160, 1440, 1080, 720, 480, 360, 240)


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
    """Return 'Best' plus preset tiers at or below the video's max height."""
    return qualities_from_info(extract_info(url))


def qualities_from_info(info: dict | None) -> list[str]:
    """Derive the quality selector list from an already-fetched ``info`` dict.

    Each tier is a height *threshold*, not an exact resolution: a 1080p video
    yields Best, 1080p, 720p, ... and never 1440p/2160p, because no format
    reaches those heights. Passing the caller's existing ``info`` avoids a
    second costly ``extract_info`` call.
    """
    if not info:
        return ["Best"]

    heights: set[int] = set()
    for fmt in info.get("formats", []):
        h = fmt.get("height")
        if h:
            heights.add(h)

    return ["Best"] + [
        f"{h}p" for h in _QUALITY_THRESHOLDS if any(x >= h for x in heights)
    ]


def extract_thumbnail(info: dict) -> str | None:
    return info.get("thumbnail") or None


def extract_title(info: dict) -> str:
    return info.get("title") or ""


def extract_duration(info: dict) -> int:
    return info.get("duration") or 0


def extract_uploader(info: dict) -> str:
    return info.get("uploader") or ""


def _pick_thumbnail(info: dict) -> str | None:
    t = info.get("thumbnail")
    if t:
        return str(t)
    thumbs = info.get("thumbnails") or []
    for t in reversed(thumbs):
        if isinstance(t, dict) and t.get("url"):
            return str(t["url"])
    return None


def extract_playlist(url: str) -> dict | None:
    """Fetch a playlist's entry list quickly via flat extraction.

    Returns a normalized dict:
        {id, title, uploader, count, thumbnail, entries: [{index, id, title,
          duration, thumbnail, url}]}
    or None when the extraction fails. Each entry's `url` is a plain watch
    URL so a single-video download can run per entry (with --no-playlist).
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": str(BIN_DIR.resolve()),
        "extract_flat": True,
        "noplaylist": False,
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None

    entries = info.get("entries") or []
    normalized = [
        {
            "index": i + 1,
            "id": e.get("id") or "",
            "title": e.get("title") or "بدون عنوان",
            "duration": e.get("duration") or 0,
            "thumbnail": _pick_thumbnail(e),
            "url": e.get("url")
            or e.get("webpage_url")
            or (f"https://www.youtube.com/watch?v={e.get('id')}" if e.get("id") else ""),
        }
        for i, e in enumerate(entries)
        if e and e.get("id")
    ]
    return {
        "id": info.get("id") or "",
        "title": info.get("title") or "قائمة تشغيل",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "count": len(normalized),
        "thumbnail": _pick_thumbnail(info),
        "entries": normalized,
    }
