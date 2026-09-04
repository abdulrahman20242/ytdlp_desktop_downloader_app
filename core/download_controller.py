import threading
import queue
from pathlib import Path
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError, UnsupportedError


class DownloadController:
    def __init__(self, config):
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._after_id = None
        self.config = config
        self._app = None
        self._callbacks = {}

    def set_app(self, app):
        self._app = app

    def on(self, event: str, callback):
        self._callbacks[event] = callback

    def start_download(self, url: str, opts: dict, save_dir: Path):
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._download_worker,
            args=(url, opts, save_dir),
            daemon=True,
        )
        self._thread.start()
        self._poll_queue()

    def _download_worker(self, url: str, opts: dict, save_dir: Path):
        import os
        # تأكد إن bin/ موجود في PATH قبل إنشاء YoutubeDL
        # (get_common_opts بيعمله، لكن هنا كـ safety net لو اتسمى الـ worker قبله)
        ffmpeg_loc = opts.get("ffmpeg_location", "")
        if ffmpeg_loc and ffmpeg_loc not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_loc + os.pathsep + os.environ.get("PATH", "")

        opts["progress_hooks"] = [self._progress_hook]
        opts["logger"] = self._get_logger()
        opts["outtmpl"] = str(save_dir / "%(title)s [%(id)s].%(ext)s")

        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([url])
            self._queue.put(("done", None))
        except DownloadError as e:
            msg = str(e)
            if "Sign in" in msg or "age" in msg.lower():
                self._queue.put(("error", "age_restricted"))
            elif "unavailable" in msg.lower():
                self._queue.put(("error", "unavailable"))
            elif "429" in msg:
                self._queue.put(("error", "rate_limited"))
            elif "cookie" in msg.lower() or "Could not copy" in msg:
                self._queue.put(("error", "فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات"))
            else:
                self._queue.put(("error", f"download_error:{msg}"))
        except ExtractorError as e:
            self._queue.put(("error", f"extractor:{e}"))
        except UnsupportedError:
            self._queue.put(("error", "unsupported_url"))
        except Exception as e:
            self._queue.put(("error", f"unknown:{e}"))

    def _progress_hook(self, d: dict):
        self._queue.put(("progress", d))

    def _get_logger(self):
        from utils.ui_logger import UILogger
        return UILogger(self._queue)

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
        except queue.Empty:
            pass

        if self._app and hasattr(self._app, "after"):
            self._after_id = self._app.after(100, self._poll_queue)

    def cancel(self):
        self._stop_event.set()
        if self._after_id and self._app:
            try:
                self._app.after_cancel(self._after_id)
            except Exception:
                pass

    def is_downloading(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
