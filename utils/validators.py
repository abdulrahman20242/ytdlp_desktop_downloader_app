import re

YOUTUBE_RE = re.compile(
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"(?:youtube\.com|youtu\.be)"
    r"(?:/watch\?v=|/embed/|/v/|/shorts/|/playlist\?list=|/watch\?.*list=)"
    r"([\w-]{11})?"
)

PLAYLIST_RE = re.compile(
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"youtube\.com/.*"
    r"[?&]list="
    r"([\w-]+)"
)


def is_valid_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_RE.match(url.strip()))


def is_playlist_url(url: str) -> bool:
    return bool(PLAYLIST_RE.search(url.strip()))


def extract_video_id(url: str) -> str | None:
    match = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})", url)
    return match.group(1) if match else None
