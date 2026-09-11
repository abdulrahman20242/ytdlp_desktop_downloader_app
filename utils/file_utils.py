import os
import re
from pathlib import Path


def ensure_dir(path: Path, fallback: Path | None = None) -> Path:
    """Create ``path`` (with parents) and return it.

    When the directory cannot be created - e.g. the target already exists as a
    plain file, or the OS denies the write - and ``fallback`` is provided, the
    fallback directory is created and returned instead. Without a fallback the
    original ``OSError`` propagates to the caller.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError:
        if fallback is None:
            raise
    try:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    except OSError:
        raise


def open_folder(path: Path):
    os.startfile(str(path.resolve()))


def get_downloads_dir() -> Path:
    return Path.home() / "Downloads" / "YTDownloader"


def safe_filename(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        name = name.replace(c, "_")
    return name.strip()


_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}


def sanitize_folder_name(name: str, fallback: str = "Playlist") -> str:
    """Turn a free-text title into a safe Windows folder name.

    Handles invalid characters, control chars, trailing dots/spaces,
    reserved device names, and length limits. Returns ``fallback`` when
    nothing usable remains.
    """
    if not name:
        return fallback

    out = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    out = re.sub(r"\s+", " ", out).strip()
    out = out.rstrip(". ")  # Windows rejects trailing dots/spaces

    base = out.split(".", 1)[0].upper()
    if base in _RESERVED_NAMES:
        out = "_" + out

    out = out[:80].rstrip(". ")
    return out or fallback
