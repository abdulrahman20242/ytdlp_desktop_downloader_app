"""Central, frozen-aware path resolution.

Every location the app touches flows through this module so the packaged
(PyInstaller onedir) build behaves exactly like the source checkout:

* ``app_root`` / ``bin_dir`` / ``assets_dir`` are read-only application
  resources that live *next to the executable* (never inside ``_internal``).
* ``user_data_dir`` holds writable per-user files (``config.json``,
  ``cookies.txt``) under ``%APPDATA%`` so the app stays movable and never
  writes into its own install directory.
"""

import os
import sys
from pathlib import Path

APP_DIR_NAME = "YTDownloader"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Directory that holds the application's resources.

    Source checkout: the project root (parent of ``utils/``).
    Frozen onedir build: the folder containing ``YTDownloaderCore.exe``.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bin_dir() -> Path:
    """Read-only folder with the bundled ``yt-dlp.exe``/``ffmpeg.exe``/
    ``ffprobe.exe``/``node.exe`` binaries."""
    return app_root() / "bin"


def assets_dir() -> Path:
    """Read-only folder with static resources such as the window icon."""
    return app_root() / "assets"


def user_data_dir() -> Path:
    """Writable per-user data directory used for config and cookies.

    Defaults to ``%APPDATA%\\YTDownloader``; falls back to a dot-folder in
    the user profile when ``%APPDATA%`` is unavailable.
    """
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home()
    candidate = root / APP_DIR_NAME
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        fallback = Path.home() / f".{APP_DIR_NAME.lower()}"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def config_path() -> Path:
    return user_data_dir() / "config.json"


def cookies_path() -> Path:
    return user_data_dir() / "cookies.txt"