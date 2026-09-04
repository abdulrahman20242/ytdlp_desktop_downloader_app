import os
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def open_folder(path: Path):
    os.startfile(str(path.resolve()))


def get_downloads_dir() -> Path:
    return Path.home() / "Downloads" / "YTDownloader"


def safe_filename(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        name = name.replace(c, "_")
    return name.strip()
