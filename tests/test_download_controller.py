import queue
import threading
from pathlib import Path

import pytest
from yt_dlp.utils import DownloadError, ExtractorError, UnsupportedError

from core.download_controller import DownloadController


class _FakeYDL:
    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def download(self, urls):
        raise NotImplementedError


class _FakeApp:
    def __init__(self):
        self._after_called = []
        self._cancelled = []

    def after(self, delay, callback):
        self._after_called.append((delay, callback))
        return 42

    def after_cancel(self, _id):
        self._cancelled.append(_id)


def _bare_controller():
    c = object.__new__(DownloadController)
    c._queue = queue.Queue()
    c._thread = None
    c._stop_event = threading.Event()
    c._after_id = None
    c._app = None
    c._callbacks = {}
    return c


def _drain(q):
    out = []
    while True:
        try:
            out.append(q.get_nowait())
        except queue.Empty:
            return out


def test_start_download_spawns_thread_and_schedules_after(tmp_path, monkeypatch):
    import core.download_controller as dc

    release = threading.Event()
    started = threading.Event()

    class BlockingYDL(_FakeYDL):
        def __init__(self, opts=None):
            super().__init__(opts or {})
            started.set()
            release.wait(timeout=5)

        def download(self, urls):
            release.wait(timeout=5)

    fake_app = _FakeApp()
    c = DownloadController(config=None)
    c.set_app(fake_app)
    c._queue = queue.Queue()
    c._thread = None

    monkeypatch.setattr(dc, "YoutubeDL", lambda opts=None, **k: BlockingYDL(opts))
    c.start_download("https://youtu.be/x", {"format": "best"}, tmp_path)
    assert started.wait(timeout=5)  # worker thread actually entered YDL
    assert c.is_downloading() is True
    assert any(delay == 100 for delay, _ in fake_app._after_called)
    release.set()


def test_download_worker_success_pushes_done(monkeypatch):
    import core.download_controller as dc

    class OkYDL(_FakeYDL):
        def download(self, urls):
            pass

    monkeypatch.setattr(dc, "YoutubeDL", lambda opts=None, **k: OkYDL(opts or {}))
    dt = _bare_controller()
    dt._download_worker("https://youtu.be/x", {"format": "best"}, Path("."))
    events = _drain(dt._queue)
    assert ("done", None) in events


@pytest.mark.parametrize(
    ("exc", "expected_prefix"),
    [
        (DownloadError("Sign in to confirm"), "age_restricted"),
        (DownloadError("This video is age restricted"), "age_restricted"),
        (DownloadError("Video unavailable"), "unavailable"),
        (DownloadError("HTTP Error 429"), "rate_limited"),
        (DownloadError("Could not copy cookie jar"), "فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات"),
        (DownloadError("some other failure"), "download_error:some other failure"),
        (RuntimeError("boom"), "unknown:boom"),
    ],
)
def test_download_worker_classifies_errors(monkeypatch, exc, expected_prefix):
    import core.download_controller as dc

    class BoomYDL(_FakeYDL):
        def download(self, urls):
            raise exc

    monkeypatch.setattr(dc, "YoutubeDL", lambda opts=None, **k: BoomYDL(opts or {}))
    dt = _bare_controller()
    dt._download_worker("https://youtu.be/x", {"format": "best"}, Path("."))
    events = _drain(dt._queue)
    errors = [data for event, data in events if event == "error"]
    assert len(errors) == 1
    assert errors[0] == expected_prefix


def test_extractor_error_is_prefixed_with_suffix_in_message(monkeypatch):
    import core.download_controller as dc

    class BoomYDL(_FakeYDL):
        def download(self, urls):
            raise ExtractorError("extractor blew up")

    monkeypatch.setattr(dc, "YoutubeDL", lambda opts=None, **k: BoomYDL(opts or {}))
    dt = _bare_controller()
    dt._download_worker("https://youtu.be/x", {"format": "best"}, Path("."))
    events = _drain(dt._queue)
    errors = [data for event, data in events if event == "error"]
    assert len(errors) == 1
    # yt-dlp appends boilerplate to ExtractorError messages
    assert errors[0].startswith("extractor:extractor blew up; please report this issue")


def test_unsupported_error_is_caught_as_extractor_error(monkeypatch):
    # In yt-dlp, UnsupportedError subclasses ExtractorError, so the
    # except UnsupportedError branch in _download_worker is unreachable and
    # the "unsupported_url" sentinel never fires. Kept as a regression test.
    import core.download_controller as dc

    class BoomYDL(_FakeYDL):
        def download(self, urls):
            raise UnsupportedError("https://bad")

    monkeypatch.setattr(dc, "YoutubeDL", lambda opts=None, **k: BoomYDL(opts or {}))
    dt = _bare_controller()
    dt._download_worker("https://youtu.be/x", {"format": "best"}, Path("."))
    events = _drain(dt._queue)
    errors = [data for event, data in events if event == "error"]
    assert len(errors) == 1
    assert errors[0] == "extractor:Unsupported URL: https://bad"


def test_download_worker_pushes_progress_events(monkeypatch):
    import core.download_controller as dc

    received_hooks = []

    class HookYDL(_FakeYDL):
        def download(self, urls):
            for hook in self.opts["progress_hooks"]:
                hook({"status": "downloading", "downloaded_bytes": 10, "total_bytes": 100})

    def fake_ydl(opts=None, **k):
        obj = HookYDL(opts or {})
        received_hooks.append(obj.opts)
        return obj

    monkeypatch.setattr(dc, "YoutubeDL", fake_ydl)
    dt = _bare_controller()
    dt._download_worker("https://youtu.be/x", {"format": "best"}, Path("."))
    events = _drain(dt._queue)
    progress = [data for event, data in events if event == "progress"]
    assert len(progress) == 1
    assert progress[0]["status"] == "downloading"
    # outtmpl is set as a side effect so filename paths resolve
    assert "outtmpl" in received_hooks[0]


def test_poll_queue_dispatches_progress_log_and_done():
    dt = _bare_controller()
    app = _FakeApp()
    dt._app = app
    received = {"progress": [], "log": [], "done": False, "error": None}
    dt._callbacks["progress"] = lambda d: received["progress"].append(d)
    dt._callbacks["log"] = lambda m: received["log"].append(m)
    dt._callbacks["done"] = lambda: received.update(done=True)
    dt._callbacks["error"] = lambda d: received.update(error=d)

    dt._queue.put(("progress", {"pct": 1}))
    dt._queue.put(("log", "hello"))
    dt._queue.put(("done", None))

    dt._poll_queue()
    assert received["progress"] == [{"pct": 1}]
    assert received["log"] == ["hello"]
    assert received["done"] is True
    assert received["error"] is None


def test_poll_queue_dispatches_error_and_stops():
    dt = _bare_controller()
    app = _FakeApp()
    dt._app = app
    received = {"error": None}
    dt._callbacks["error"] = lambda d: received.update(error=d)

    dt._queue.put(("error", "age_restricted"))
    dt._poll_queue()
    assert received["error"] == "age_restricted"


def test_poll_queue_reschedules_when_only_progress():
    dt = _bare_controller()
    app = _FakeApp()
    dt._app = app
    dt._queue.put(("progress", {"pct": 1}))
    dt._poll_queue()
    assert app._after_called == [(100, dt._poll_queue)]


def test_poll_queue_returns_without_rescheduling_after_done():
    dt = _bare_controller()
    app = _FakeApp()
    dt._app = app
    dt._queue.put(("done", None))
    dt._poll_queue()
    assert app._after_called == []


def test_cancel_stops_and_cancels_pending_after():
    c = DownloadController(config=None)
    c._queue = queue.Queue()
    fake = _FakeApp()
    c._app = fake
    c._after_id = 99
    c.cancel()
    assert c._stop_event.is_set()
    assert fake._cancelled == [99]


def test_is_downloading_reflects_thread_state():
    c = DownloadController(config=None)
    c._queue = queue.Queue()
    assert c.is_downloading() is False

    t = threading.Thread(target=lambda: threading.Event().wait(5), daemon=True)
    t.start()
    c._thread = t
    assert c.is_downloading() is True
    t.join(timeout=0.01)