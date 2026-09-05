import os
import queue
import re
import subprocess
import threading
from pathlib import Path


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_PROGRESS_RE = re.compile(r"\[download\]\s+([\d.]+)%")
_SPEED_RE = re.compile(r"\bat\s+([^\s]+)\s+ETA")
_ETA_RE = re.compile(r"ETA\s+([^\s)]+)")


def _strip_ansi(line: str) -> str:
    return _ANSI_RE.sub("", line)


def _strip_ytdlp_report_suffix(msg: str) -> str:
    marker = "; please report this issue"
    if marker in msg:
        msg = msg.split(marker, 1)[0]
    return msg.strip()


def _classify_error(msg: str) -> str:
    low = msg.lower()
    if "sign in" in low or "age" in low:
        return "age_restricted"
    if "unavailable" in low:
        return "unavailable"
    if "429" in msg:
        return "rate_limited"
    if "cookie" in low or "could not copy" in low:
        return "فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات"
    if "unsupported url" in low:
        return "unsupported_url"
    if "; please report this issue" in msg:
        return f"extractor:{_strip_ytdlp_report_suffix(msg)}"
    return f"download_error:{msg}"


def _parse_progress(line: str) -> dict | None:
    m = _PROGRESS_RE.search(line)
    if not m:
        return None
    pct = float(m.group(1))
    done = pct >= 100.0
    d = {
        "status": "finished" if done else "downloading",
        "_percent_str": f"{m.group(1)}%",
        "downloaded_bytes": 1 if done else 0,
        "total_bytes": 1 if done else None,
        "_speed_str": "N/A",
        "_eta_str": "N/A",
    }
    sp = _SPEED_RE.search(line)
    if sp:
        d["_speed_str"] = sp.group(1)
    eta = _ETA_RE.search(line)
    if eta:
        d["_eta_str"] = eta.group(1)
    return d


def _parse_destination(line: str) -> str | None:
    m = re.search(r"\[download\]\s*Destination:\s*(.+)", line)
    if m:
        return m.group(1).strip()
    return None


def _build_argv(opts: dict, url: str, save_dir: Path) -> list[str]:
    base_bin = Path(__file__).resolve().parent.parent / "bin"
    ffmpeg = opts.get("ffmpeg_location")
    ffmpeg_dir = Path(ffmpeg) if ffmpeg else base_bin

    args = []

    fmt = opts.get("format")
    if fmt:
        args += ["-f", fmt]

    for pp in opts.get("postprocessors", []) or []:
        key = pp.get("key")
        if key == "FFmpegExtractAudio":
            args += ["-x", "--audio-format", pp.get("preferredcodec", "mp3")]
            q = pp.get("preferredquality")
            if q:
                args += ["--audio-quality", str(q)]
        elif key == "FFmpegMetadata":
            args += ["--add-metadata"]
        elif key == "EmbedThumbnail":
            args += ["--embed-thumbnail"]

    if opts.get("writethumbnail"):
        args += ["--write-thumbnail"]

    if opts.get("merge_output_format"):
        args += ["--merge-output-format", str(opts["merge_output_format"])]

    if opts.get("noplaylist"):
        args += ["--no-playlist"]

    if ffmpeg:
        args += ["--ffmpeg-location", str(ffmpeg_dir)]

    n = opts.get("concurrent_fragments")
    if n is not None:
        args += ["--concurrent-fragments", str(n)]

    for key, flag in (("retries", "--retries"), ("fragment_retries", "--fragment-retries")):
        v = opts.get(key)
        if v is not None:
            args += [flag, str(v)]

    if opts.get("throttledratelimit"):
        args += ["--throttled-rate", str(opts["throttledratelimit"])]

    fs = opts.get("format_sort")
    if fs:
        args += ["--format-sort", ",".join(fs) if isinstance(fs, (list, tuple)) else str(fs)]

    js = opts.get("js_runtimes")
    if isinstance(js, dict) and js:
        runtimes = []
        for name, cfg in js.items():
            if name == "node":
                runtimes.append(f"node:{ffmpeg_dir / 'node.exe'}")
            elif isinstance(cfg, dict) and cfg.get("path"):
                runtimes.append(f"{name}:{cfg['path']}")
            else:
                runtimes.append(name)
        if runtimes:
            args += ["--js-runtimes", ",".join(runtimes)]

    ext_args = opts.get("extractor_args")
    if isinstance(ext_args, dict):
        entries = []
        for ie, cfg in ext_args.items():
            if not cfg:
                continue
            if isinstance(cfg, dict):
                kv_parts = []
                for k, v in cfg.items():
                    if isinstance(v, (list, tuple)):
                        kv_parts.append(f"{k}={','.join(str(x) for x in v)}")
                    else:
                        kv_parts.append(f"{k}={v}")
                entries.append(f"{ie}:{';'.join(kv_parts)}")
            else:
                entries.append(f"{ie}:{cfg}")
        if entries:
            args += ["--extractor-args", ";".join(entries)]

    cfb = opts.get("cookiesfrombrowser")
    if cfb:
        args += ["--cookies-from-browser", cfb[0] if isinstance(cfb, (list, tuple)) else str(cfb)]

    cookie_file = opts.get("cookiefile")
    if cookie_file:
        args += ["--cookies", str(cookie_file)]

    if opts.get("sponsorblock_remove"):
        remove = opts.get("sponsorblock_remove")
        cats = opts.get("sponsorblock_categories")
        if isinstance(remove, (list, tuple)):
            cats = remove
        cats = cats or ["sponsor"]
        args += ["--sponsorblock-remove", ",".join(cats)]

    outtmpl = opts.get("outtmpl") or str(Path(save_dir) / "%(title)s [%(id)s].%(ext)s")
    args += ["-o", outtmpl]

    if opts.get("quiet", True):
        args += ["--quiet"]
    if opts.get("no_warnings", True):
        args += ["--no-warnings"]
    if opts.get("verbose"):
        args += ["--verbose"]

    args += ["--newline", "--progress"]
    args.append(url)
    return args


class DownloadController:
    def __init__(self, config):
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._after_id = None
        self._proc = None
        self.config = config
        self._app = None
        self._callbacks = {}

    def set_app(self, app):
        self._app = app

    def on(self, event: str, callback):
        self._callbacks[event] = callback

    def start_download(self, url: str, opts: dict, save_dir: Path):
        self._stop_event.clear()
        self._proc = None
        self._thread = threading.Thread(
            target=self._download_worker,
            args=(url, opts, save_dir),
            daemon=True,
        )
        self._thread.start()
        self._poll_queue()

    def start_playlist_download(self, entries: list[dict], opts: dict, save_dir: Path):
        self._stop_event.clear()
        self._proc = None
        self._thread = threading.Thread(
            target=self._playlist_worker,
            args=(list(entries), opts, Path(save_dir)),
            daemon=True,
        )
        self._thread.start()
        self._poll_queue()

    def _exe_path(self, opts: dict | None = None) -> Path:
        base = Path(__file__).resolve().parent.parent / "bin"
        ffmpeg = (opts or {}).get("ffmpeg_location")
        if ffmpeg:
            base = Path(ffmpeg)
        return base / "yt-dlp.exe"

    # ------------------------------------------------------------------ #
    #  Internal: run a single yt-dlp invocation, return result string
    # ------------------------------------------------------------------ #

    def _run_single(self, url: str, opts: dict, save_dir: Path, index=None) -> str:
        ffmpeg_loc = opts.get("ffmpeg_location", "")
        if ffmpeg_loc and ffmpeg_loc not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_loc + os.pathsep + os.environ.get("PATH", "")

        argv = _build_argv(opts, url, Path(save_dir))
        try:
            proc = subprocess.Popen(
                [str(self._exe_path(opts)), *argv],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as e:
            return f"unknown:{e}"
        self._proc = proc

        first_error = None
        filename = ""
        try:
            for raw in proc.stdout:
                if self._stop_event.is_set():
                    break
                line = _strip_ansi(raw).rstrip("\r\n")
                if not line:
                    continue
                if line.startswith("ERROR:"):
                    if first_error is None:
                        first_error = line[len("ERROR:"):].strip()
                    self._queue.put(("log", f"[ERROR] {line}"))
                    continue
                if line.startswith("WARNING:"):
                    self._queue.put(("log", f"[WARN] {line}"))
                    continue
                dest = _parse_destination(line)
                if dest:
                    filename = dest
                    continue
                prog = _parse_progress(line)
                if prog:
                    prog["filename"] = filename or ""
                    if index is not None:
                        prog["index"] = index
                    self._queue.put(("progress", prog))
                elif line.startswith("["):
                    self._queue.put(("log", f"[INFO] {line}"))
        finally:
            self._proc = None
            if proc.poll() is None:
                proc.terminate()

        if self._stop_event.is_set():
            return "cancelled"

        rc = proc.wait()
        if rc == 0 and first_error is None:
            return "ok"

        msg = first_error or f"yt-dlp exited with code {rc}"
        return _classify_error(msg)

    # ------------------------------------------------------------------ #
    #  Workers
    # ------------------------------------------------------------------ #

    def _download_worker(self, url: str, opts: dict, save_dir: Path):
        result = self._run_single(url, opts, save_dir)
        if self._stop_event.is_set():
            return
        if result == "ok":
            self._queue.put(("done", None))
        else:
            self._queue.put(("error", result))

    def _playlist_worker(self, entries: list[dict], opts: dict, save_dir: Path):
        total = len(entries)
        if total == 0:
            self._queue.put(("playlist_done", None))
            return

        for pos, entry in enumerate(entries, 1):
            if self._stop_event.is_set():
                return

            index = entry.get("index", pos)
            item_id = entry.get("id", "")
            url = (
                entry.get("url")
                or (f"https://www.youtube.com/watch?v={item_id}" if item_id else "")
            )
            if not url:
                self._queue.put((
                    "playlist_item",
                    {"index": index, "id": item_id, "status": "failed",
                     "error": "الرابط غير متاح", "position": pos, "total": total},
                ))
                continue

            self._queue.put((
                "playlist_item",
                {"index": index, "id": item_id, "status": "downloading",
                 "position": pos, "total": total},
            ))

            result = self._run_single(url, opts, save_dir, index=index)

            if self._stop_event.is_set():
                return

            self._queue.put((
                "playlist_item",
                {"index": index, "id": item_id,
                 "status": "completed" if result == "ok" else "failed",
                 "error": None if result == "ok" else result,
                 "position": pos, "total": total},
            ))

        if not self._stop_event.is_set():
            self._queue.put(("playlist_done", None))

    # ------------------------------------------------------------------ #
    #  Event loop
    # ------------------------------------------------------------------ #

    def _poll_queue(self):
        try:
            while True:
                event, data = self._queue.get_nowait()
                if event == "progress":
                    cb = self._callbacks.get("progress")
                    if cb:
                        cb(data)
                elif event == "done":
                    cb = self._callbacks.get("done")
                    if cb:
                        cb()
                    return
                elif event == "error":
                    cb = self._callbacks.get("error")
                    if cb:
                        cb(data)
                    return
                elif event == "log":
                    cb = self._callbacks.get("log")
                    if cb:
                        cb(data)
                elif event == "playlist_item":
                    cb = self._callbacks.get("playlist_item")
                    if cb:
                        cb(data)
                elif event == "playlist_done":
                    cb = self._callbacks.get("playlist_done")
                    if cb:
                        cb()
                    return
        except queue.Empty:
            pass

        if self._app and hasattr(self._app, "after"):
            self._after_id = self._app.after(100, self._poll_queue)

    def cancel(self):
        self._stop_event.set()
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
        if self._after_id and self._app:
            try:
                self._app.after_cancel(self._after_id)
            except Exception:
                pass

    def is_downloading(self) -> bool:
        return self._thread is not None and self._thread.is_alive()