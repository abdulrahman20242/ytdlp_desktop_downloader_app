import re

YOUTUBE_RE = re.compile(
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"(?:youtube\.com|youtu\.be)"
    r"(?:"
    r"(?:/watch\?(?:[^#?]*?[?&])?v=([\w-]{11})(?![\w-])(?:[&#][^#]*)?)"
    r"|/(?:embed/|v/|shorts/)([\w-]{11})(?![\w-])(?:[?#][^#]*)?"
    r"|/playlist\?list=[\w-]+"
    r"|/watch\?.*list=[\w-]+"
    r"|/([\w-]{11})(?![\w-])"
    r")"
)

PLAYLIST_RE = re.compile(
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"(?:youtube\.com|youtu\.be)/.*"
    r"[?&]list="
    r"([\w-]+)"
)

# Explicit playlist links only: the URL's path is /playlist (never a watch page).
# A watch/shorts/embed URL that merely carries an extra list= param is NOT a
# playlist request — it must keep behaving as a single-video download.
EXPLICIT_PLAYLIST_RE = re.compile(
    r"(?:https?://)?"
    r"(?:www\.)?"
    r"(?:youtube\.com|youtu\.be)"
    r"/playlist(?:[?#][^#]*)?"
    r"[?&]list=[\w-]+"
)


def is_valid_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_RE.match(url.strip()))


def is_playlist_url(url: str) -> bool:
    return bool(PLAYLIST_RE.search(url.strip()))


def is_explicit_playlist_url(url: str) -> bool:
    """True only for youtube.com/playlist?list=... links."""
    return bool(EXPLICIT_PLAYLIST_RE.search(url.strip()))


def classify_url(url: str) -> str | None:
    """Return 'playlist' for explicit playlist links, 'video' for single-video
    URLs (even when they carry playlist params), else None."""
    u = url.strip()
    if is_explicit_playlist_url(u):
        return "playlist"
    if is_valid_youtube_url(u):
        return "video"
    return None


def extract_video_id(url: str) -> str | None:
    match = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})(?![\w-])", url)
    return match.group(1) if match else None
