import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass


@dataclass
class DepResult:
    name: str
    found: bool
    path: str | None
    version: str | None
    required: bool


class DependencyChecker:
    BIN_DIR = Path(__file__).resolve().parent.parent / "bin"

    def check_all(self) -> list[DepResult]:
        return [
            self._check_ffmpeg(),
            self._check_ffprobe(),
            self._check_node(),
            self._check_ytdlp(),
        ]

    def _check_ffmpeg(self) -> DepResult:
        path = self.BIN_DIR / "ffmpeg.exe"
        if not path.exists():
            path = shutil.which("ffmpeg")
        if path:
            try:
                out = subprocess.check_output(
                    [str(path), "-version"], stderr=subprocess.STDOUT, text=True
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
                    [str(path), "-version"], stderr=subprocess.STDOUT, text=True
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
                    [str(path), "--version"], text=True
                ).strip()
            except Exception:
                ver = "unknown"
            return DepResult("Node.js", True, str(path), ver, required=False)
        return DepResult("Node.js", False, None, None, required=False)

    def _check_ytdlp(self) -> DepResult:
        try:
            import yt_dlp
            ver = getattr(yt_dlp.version, "__version__", "unknown")
            return DepResult("yt-dlp", True, yt_dlp.__file__, ver, required=True)
        except ImportError:
            return DepResult("yt-dlp", False, None, None, required=True)
