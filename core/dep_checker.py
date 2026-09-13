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
        results = [
            self._check_ffmpeg(),
            self._check_ffprobe(),
            self._check_node(),
            self._check_ytdlp(),
            self._check_ytdlp_python(),
        ]

        mismatch = self._check_version_consistency(results)
        if mismatch is not None:
            results.append(mismatch)

        return results

    @staticmethod
    def _check_version_consistency(results: list["DepResult"]) -> "DepResult | None":
        """Warn when the bundled yt-dlp.exe and the Python yt_dlp package
        report different versions.  A mismatch can cause metadata extraction
        to advertise qualities or formats that the download engine cannot
        satisfy."""
        exe_ver = None
        py_ver = None
        for dep_result in results:
            if dep_result.name == "yt-dlp" and dep_result.found and dep_result.version:
                exe_ver = dep_result.version.strip()
            elif dep_result.name == "yt-dlp Python package" and dep_result.found and dep_result.version:
                py_ver = dep_result.version.strip()

        if exe_ver and py_ver and exe_ver != py_ver:
            return DepResult(
                name="yt-dlp version sync",
                found=True,
                path=None,
                version=f"EXE={exe_ver}  ≠  Python={py_ver}",
                required=False,
            )
        return None

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
            except (OSError, subprocess.SubprocessError):
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
            except (OSError, subprocess.SubprocessError):
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
            except (OSError, subprocess.SubprocessError):
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
