import os
import shutil
import subprocess
from dataclasses import dataclass

from utils.paths import bin_dir

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


@dataclass
class DepResult:
    name: str
    found: bool
    path: str | None
    version: str | None
    required: bool


class DependencyChecker:
    BIN_DIR = bin_dir()

    def check_all(self) -> list[DepResult]:
        return [
            self._check_ffmpeg(),
            self._check_ffprobe(),
            self._check_node(),
            self._check_ytdlp(),
            self._check_ytdlp_python(),
        ]

    def _check_ffmpeg(self) -> DepResult:
        path = self.BIN_DIR / "ffmpeg.exe"
        if not path.exists():
            path = shutil.which("ffmpeg")
        if path:
            try:
                out = subprocess.check_output(
                    [str(path), "-version"],
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=_CREATE_NO_WINDOW,
                )
                version = out.split("\n")[0] if out else "unknown"
            except Exception:
                version = "unknown"
            return DepResult("FFmpeg", True, str(path), version, required=True)
        return DepResult("FFmpeg", False, None, None, required=True)

    def _check_ffprobe(self) -> DepResult:
        path = self.BIN_DIR / "ffprobe.exe"
        if not path.exists():
            path = shutil.which("ffprobe")
        if path:
            try:
                out = subprocess.check_output(
                    [str(path), "-version"],
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=_CREATE_NO_WINDOW,
                )
                version = out.split("\n")[0] if out else "unknown"
            except Exception:
                version = "unknown"
            return DepResult("FFprobe", True, str(path), version, required=True)
        return DepResult("FFprobe", False, None, None, required=True)

    def _check_node(self) -> DepResult:
        path = self.BIN_DIR / "node.exe"
        if not path.exists():
            path = shutil.which("node")
        if path:
            try:
                ver = subprocess.check_output(
                    [str(path), "--version"],
                    text=True,
                    creationflags=_CREATE_NO_WINDOW,
                ).strip()
            except Exception:
                ver = "unknown"
            return DepResult("Node.js", True, str(path), ver, required=False)
        return DepResult("Node.js", False, None, None, required=False)

    def _check_ytdlp(self) -> DepResult:
        path = self.BIN_DIR / "yt-dlp.exe"
        if not path.exists():
            return DepResult("yt-dlp", False, None, None, required=True)
        try:
            completed = subprocess.run(
                [str(path), "--version"], capture_output=True, text=True,
                creationflags=_CREATE_NO_WINDOW, timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return DepResult("yt-dlp", False, None, None, required=True)
        if completed.returncode != 0:
            return DepResult("yt-dlp", False, str(path), None, required=True)
        output = completed.stdout.strip()
        version = output.splitlines()[0] if output else "unknown"
        return DepResult("yt-dlp", True, str(path), version, required=True)

    @staticmethod
    def _check_ytdlp_python() -> DepResult:
        try:
            import yt_dlp
            version = getattr(yt_dlp.version, "__version__", "unknown")
            return DepResult("yt-dlp Python package", True, yt_dlp.__file__, version, required=True)
        except ImportError:
            return DepResult("yt-dlp Python package", False, None, None, required=True)
