import queue
import threading
from pathlib import Path

import pytest

from core.download_controller import (
    DownloadController,
    _build_argv,
    _classify_error,
    _parse_destination,
    _parse_progress,
    _strip_ytdlp_report_suffix,
)


class _FakeProc:
    def __init__(self, lines, rc=0):
        self.lines = list(lines)
        self.stdout = iter(self.lines)
        self.rc = rc
        self.terminated = False

    def poll(self):
        return self.rc

    def wait(self):
        return self.rc

    def terminate(self):
        self.terminated = True


class _BlockingProc(_FakeProc):
    def __init__(self, lines, started, release, rc=0):
        self.lines = list(lines)
        self.rc = rc
        self.terminated = False
        self._started = started
        self._release = release

    @property
    def stdout(self):
        self._started.set()
        self._release.wait(timeout=5)
        return iter(self.lines)


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
    c._proc = None
    c._app = None
    c._callbacks = {}
    return c


def _worker_with_stdout(monkeypatch, lines, rc=0, opts=None):
    dt = _bare_controller()
    proc = _FakeProc(lines, rc=rc)
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: proc)
    dt._download_worker("https://youtu.be/x", opts or {"format": "best"}, Path("."))
    return dt, proc


def _drain(q):
    out = []
    while True:
        try:
            out.append(q.get_nowait())
        except queue.Empty:
            return out


def test_start_download_spawns_thread_and_schedules_after(tmp_path, monkeypatch):
    release = threading.Event()
    started = threading.Event()

    proc = _BlockingProc([], started, release, rc=0)
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: proc)

    fake_app = _FakeApp()
    c = DownloadController(config=None)
    c.set_app(fake_app)
    c._queue = queue.Queue()
    c._thread = None

    c.start_download("https://youtu.be/x", {"format": "best"}, tmp_path)
    assert started.wait(timeout=5)  # worker thread actually spawned the exe
    assert c.is_downloading() is True
    assert any(delay == 100 for delay, _ in fake_app._after_called)
    release.set()
    if c._thread:
        c._thread.join(timeout=1)


def test_download_worker_success_pushes_done(monkeypatch):
    lines = [
        "[info] wRuQPV8Q4jc: Downloading 1 format(s): 394+251",
        "[download] Destination: out\\Graphify [wRuQPV8Q4jc].webm",
        "[download] 100% of 20.60MiB in 00:15",
    ]
    dt, _ = _worker_with_stdout(monkeypatch, lines, rc=0)
    events = _drain(dt._queue)
    assert ("done", None) in events
    assert any(e == "log" and "[info]" in d for e, d in events)


@pytest.mark.parametrize(
    ("error_line", "expected"),
    [
        ("ERROR: Sign in to confirm you're not a bot. This is to protect our users", "age_restricted"),
        ("ERROR: This video is only available to users aged 18+", "age_restricted"),
        ("ERROR: Video unavailable. This video is private.", "unavailable"),
        ("ERROR: HTTP Error 429: Too Many Requests (caused by ...)", "rate_limited"),
        (
            "ERROR: Could not copy cookie jar",
            "فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات",
        ),
        ("ERROR: Unsupported URL: https://example.com", "unsupported_url"),
        ("ERROR: some other failure", "download_error:some other failure"),
    ],
)
def test_download_worker_classifies_errors(monkeypatch, error_line, expected):
    dt, _ = _worker_with_stdout(monkeypatch, [error_line], rc=1)
    events = _drain(dt._queue)
    errors = [data for event, data in events if event == "error"]
    assert errors == [expected]


def test_extractor_error_message_strips_ytdlp_boilerplate_suffix(monkeypatch):
    line = (
        "ERROR: [youtube] wRuQPV8Q4jc: extractor blew up; please report this issue. "
        "Ensure you're using the latest version..."
    )
    dt, _ = _worker_with_stdout(monkeypatch, [line], rc=1)
    events = _drain(dt._queue)
    errors = [data for event, data in events if event == "error"]
    assert len(errors) == 1
    assert errors[0].startswith("extractor:")
    assert "please report" not in errors[0]


def test_unsupported_error_fires_unsupported_url_sentinel(monkeypatch):
    dt, _ = _worker_with_stdout(
        monkeypatch, ["ERROR: Unsupported URL: https://bad"], rc=1
    )
    events = _drain(dt._queue)
    errors = [data for event, data in events if event == "error"]
    assert errors == ["unsupported_url"]


def test_download_worker_pushes_progress_events(monkeypatch):
    lines = [
        "[info] title: Graphify - demo",
        "[download] Destination: F:\\out\\Graphify [wRuQPV8Q4jc].webm",
        "[download]  42.5% of ~20.60MiB at 1.23MiB/s ETA 00:12",
        "[download]  100% of 20.60MiB in 00:15",
    ]
    dt, _ = _worker_with_stdout(monkeypatch, lines, rc=0)
    events = _drain(dt._queue)
    progress = [data for event, data in events if event == "progress"]
    assert len(progress) == 2
    assert progress[0]["status"] == "downloading"
    assert progress[0]["_percent_str"] == "42.5%"
    assert progress[0]["_speed_str"] == "1.23MiB/s"
    assert progress[0]["_eta_str"] == "00:12"
    assert progress[0]["filename"] == "F:\\out\\Graphify [wRuQPV8Q4jc].webm"
    assert progress[1]["status"] == "finished"
    assert ("done", None) in events


def test_download_worker_reports_popen_failure(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no exe")

    monkeypatch.setattr("subprocess.Popen", boom)
    dt = _bare_controller()
    dt._download_worker("https://youtu.be/x", {"format": "best"}, Path("."))
    events = _drain(dt._queue)
    errors = [data for event, data in events if event == "error"]
    assert errors == ["unknown:no exe"]


def test_cancel_terminates_worker_mid_download(monkeypatch):
    first_seen = threading.Event()
    second = threading.Event()

    def gen():
        yield "[info] start"
        first_seen.set()
        second.wait(timeout=5)
        yield "[download]  50.0% of 20MiB"
        yield "[download] 100% of 20MiB"

    proc = _FakeProc(gen(), rc=0)
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: proc)

    dt = _bare_controller()
    t = threading.Thread(
        target=lambda: dt._download_worker("u", {"format": "best"}, Path(".")),
        daemon=True,
    )
    t.start()
    assert first_seen.wait(timeout=5)
    dt.cancel()
    second.set()
    t.join(timeout=5)
    assert t.is_alive() is False
    events = _drain(dt._queue)
    assert not any(event in ("done", "error") for event, _ in events)


def test_build_argv_basic_defaults():
    argv = _build_argv({"format": "bv*+ba/b"}, "https://youtu.be/x", Path("C:\\out"))
    assert argv[0] == "-f"
    assert argv[1] == "bv*+ba/b"
    assert "-o" in argv
    assert str(Path("C:\\out") / "%(title)s [%(id)s].%(ext)s") in argv
    for flag in ("--quiet", "--no-warnings", "--newline", "--progress"):
        assert flag in argv
    assert "--no-colors" not in argv
    assert argv[-1] == "https://youtu.be/x"


def test_build_argv_adds_no_playlist_when_requested():
    argv = _build_argv(
        {"format": "best", "noplaylist": True},
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLx9x",
        Path("."),
    )
    assert "--no-playlist" in argv
    argv2 = _build_argv({"format": "best"}, "u", Path("."))
    assert "--no-playlist" not in argv2


def test_build_argv_wires_verbose_flag():
    argv = _build_argv({"format": "best", "verbose": True}, "u", Path("."))
    assert "--verbose" in argv
    argv_off = _build_argv({"format": "best", "verbose": False}, "u", Path("."))
    assert "--verbose" not in argv_off
    argv_missing = _build_argv({"format": "best"}, "u", Path("."))
    assert "--verbose" not in argv_missing


def test_build_argv_cookies_none_injects_no_cookie_flags():
    argv = _build_argv({"format": "best"}, "u", Path("."))
    assert "--cookies-from-browser" not in argv
    assert "--cookies" not in argv


def test_build_argv_translates_format_sort_retries_and_limits():
    opts = {
        "format": "best",
        "format_sort": ["res", "proto"],
        "retries": 3,
        "fragment_retries": None,
        "throttledratelimit": 1000000,
    }
    argv = _build_argv(opts, "u", Path("."))
    assert argv[argv.index("--format-sort") + 1] == "res,proto"
    assert argv[argv.index("--retries") + 1] == "3"
    assert "--fragment-retries" not in argv
    assert argv[argv.index("--throttled-rate") + 1] == "1000000"


def test_build_argv_cookies_and_extractor_args():
    opts = {
        "format": "best",
        "cookiesfrombrowser": ["chrome"],
        "cookiefile": "data/cookies.txt",
        "extractor_args": {
            "youtube": {"player_client": ["default", "-tv"]},
            "youtube-ejs": {"POT": ["true"]},
        },
    }
    argv = _build_argv(opts, "u", Path("."))
    assert argv[argv.index("--cookies-from-browser") + 1] == "chrome"
    assert argv[argv.index("--cookies") + 1] == "data/cookies.txt"
    ea = argv[argv.index("--extractor-args") + 1]
    assert "youtube:player_client=default,-tv" in ea
    assert "youtube-ejs:POT=true" in ea


def test_build_argv_skips_empty_extractor_args():
    opts = {"format": "best", "extractor_args": {"youtube-ejs": {}}}
    argv = _build_argv(opts, "u", Path("."))
    assert "--extractor-args" not in argv


def test_build_argv_audio_postprocessors_and_merge():
    opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ],
        "merge_output_format": "mp4",
        "writethumbnail": True,
    }
    argv = _build_argv(opts, "u", Path("."))
    assert "-x" in argv
    assert argv[argv.index("--audio-format") + 1] == "mp3"
    assert argv[argv.index("--audio-quality") + 1] == "192"
    assert "--add-metadata" in argv
    assert "--embed-thumbnail" in argv
    assert "--write-thumbnail" in argv
    assert argv[argv.index("--merge-output-format") + 1] == "mp4"


def test_build_argv_js_runtimes_point_at_node_in_ffmpeg_bin(tmp_path):
    opts = {
        "format": "best",
        "ffmpeg_location": str(tmp_path),
        "js_runtimes": {"node": {"path": "ignored"}},
    }
    argv = _build_argv(opts, "u", Path("."))
    assert argv[argv.index("--js-runtimes") + 1] == f"node:{Path(tmp_path) / 'node.exe'}"
    assert argv[argv.index("--ffmpeg-location") + 1] == str(tmp_path)


def test_build_argv_sponsorblock_default_categories():
    argv = _build_argv({"format": "best", "sponsorblock_remove": ["sponsor", "intro"]}, "u", Path("."))
    assert argv[argv.index("--sponsorblock-remove") + 1] == "sponsor,intro"

    argv2 = _build_argv({"format": "best", "sponsorblock_remove": True}, "u", Path("."))
    assert argv2[argv2.index("--sponsorblock-remove") + 1] == "sponsor"


def test_parse_progress_downloading_with_speed_eta():
    d = _parse_progress("[download]  42.5% of ~20.60MiB at 1.23MiB/s ETA 00:12")
    assert d is not None
    assert d["status"] == "downloading"
    assert d["_percent_str"] == "42.5%"
    assert d["downloaded_bytes"] == 0
    assert d["total_bytes"] is None
    assert d["_speed_str"] == "1.23MiB/s"
    assert d["_eta_str"] == "00:12"


def test_parse_progress_finishes_at_100():
    d = _parse_progress("[download] 100% of 20.60MiB in 00:15")
    assert d is not None
    assert d["status"] == "finished"
    assert d["downloaded_bytes"] == 1
    assert d["total_bytes"] == 1


def test_parse_progress_ignores_non_progress_lines():
    assert _parse_progress("[info] some message") is None
    assert _parse_progress("") is None


def test_parse_destination():
    dest = _parse_destination("[download] Destination: C:\\out\\x.mp4")
    assert dest == "C:\\out\\x.mp4"
    assert _parse_destination("not a dest") is None


def test_strip_ytdlp_report_suffix():
    assert _strip_ytdlp_report_suffix("x blew up; please report this issue. See docs") == "x blew up"
    assert _strip_ytdlp_report_suffix("plain message") == "plain message"


@pytest.mark.parametrize(
    ("msg", "expected"),
    [
        ("Sign in to confirm you're not a bot", "age_restricted"),
        ("This video is age restricted", "age_restricted"),
        ("Video unavailable", "unavailable"),
        ("HTTP Error 429: Too Many Requests", "rate_limited"),
        (
            "Could not copy cookie jar",
            "فشل استخراج cookies من المتصفح — أغلق المتصفح أو استخدم ملف cookies في الإعدادات",
        ),
        ("Unsupported URL: https://bad", "unsupported_url"),
        ("extractor blew up; please report this issue. See ...", "extractor:extractor blew up"),
        ("some other failure", "download_error:some other failure"),
    ],
)
def test_classify_error(msg, expected):
    assert _classify_error(msg) == expected


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


# --------------------------------------------------------------------- #
#  Playlist orchestration
# --------------------------------------------------------------------- #


def _playlist_entries():
    return [
        {"index": 1, "id": "aaa", "url": "https://www.youtube.com/watch?v=aaa", "title": "A"},
        {"index": 3, "id": "bbb", "url": "https://www.youtube.com/watch?v=bbb", "title": "B"},
    ]


def _run_playlist_worker(monkeypatch, entries, procs_by_url):
    def fake_popen(cmd, **kwargs):
        url = cmd[-1]
        lines, rc = procs_by_url.get(url, ([], 0))
        return _FakeProc(lines, rc=rc)

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    dt = _bare_controller()
    dt._playlist_worker(entries, {"format": "best"}, Path("."))
    return dt


def test_playlist_worker_downloads_all_entries_in_order(monkeypatch):
    dt = _run_playlist_worker(
        monkeypatch,
        _playlist_entries(),
        {
            "https://www.youtube.com/watch?v=aaa": (["[download] Destination: a.mp4"], 0),
            "https://www.youtube.com/watch?v=bbb": ([], 0),
        },
    )
    events = _drain(dt._queue)
    items = [(d.get("index"), d.get("status")) for e, d in events if e == "playlist_item"]
    assert items == [
        (1, "downloading"),
        (1, "completed"),
        (3, "downloading"),
        (3, "completed"),
    ]
    assert ("playlist_done", None) in events
    assert not any(event in ("done", "error") for event, _ in events)


def test_playlist_worker_marks_failed_item_and_continues(monkeypatch):
    dt = _run_playlist_worker(
        monkeypatch,
        _playlist_entries(),
        {
            "https://www.youtube.com/watch?v=aaa": ([], 0),
            "https://www.youtube.com/watch?v=bbb": (
                ["ERROR: Video unavailable. This video is private."],
                1,
            ),
        },
    )
    events = _drain(dt._queue)
    items = [d for e, d in events if e == "playlist_item"]
    completed = [d for d in items if d["status"] == "completed"]
    failed = [d for d in items if d["status"] == "failed"]
    assert len(completed) == 1
    assert completed[0]["index"] == 1
    assert len(failed) == 1
    assert failed[0]["index"] == 3
    assert failed[0]["error"] == "unavailable"
    assert ("playlist_done", None) in events
    assert not any(event == "error" for event, _ in events)


def test_playlist_worker_skips_entry_without_url(monkeypatch):
    dt = _run_playlist_worker(
        monkeypatch,
        [
            {"index": 2, "id": "", "url": "", "title": "broken"},
            {"index": 4, "id": "ccc", "url": "https://www.youtube.com/watch?v=ccc", "title": "C"},
        ],
        {"https://www.youtube.com/watch?v=ccc": ([], 0)},
    )
    events = _drain(dt._queue)
    items = [d for e, d in events if e == "playlist_item"]
    assert items[0]["status"] == "failed"
    assert items[0]["error"] == "الرابط غير متاح"
    assert items[1]["status"] == "downloading"
    assert items[2]["status"] == "completed"
    assert ("playlist_done", None) in events


def test_playlist_worker_progress_events_carry_entry_index(monkeypatch):
    dt = _run_playlist_worker(
        monkeypatch,
        [{"index": 7, "id": "ddd", "url": "https://www.youtube.com/watch?v=ddd", "title": "D"}],
        {
            "https://www.youtube.com/watch?v=ddd": (
                [
                    "[download] Destination: out\\D.mp4",
                    "[download]  42.5% of ~20.60MiB at 1.23MiB/s ETA 00:12",
                    "[download]  100% of 20.60MiB in 00:15",
                ],
                0,
            )
        },
    )
    events = _drain(dt._queue)
    progress = [d for e, d in events if e == "progress"]
    assert progress and progress[0]["index"] == 7
    assert progress[0]["filename"] == "out\\D.mp4"
    assert progress[0]["_percent_str"] == "42.5%"


def test_cancel_during_playlist_stops_before_next_item(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    proc = _BlockingProc(["[info] start"], started, release, rc=0)
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: proc)

    dt = _bare_controller()
    t = threading.Thread(
        target=lambda: dt._playlist_worker(_playlist_entries(), {"format": "best"}, Path(".")),
        daemon=True,
    )
    t.start()
    assert started.wait(timeout=5)
    dt.cancel()
    release.set()
    t.join(timeout=5)
    assert t.is_alive() is False
    events = _drain(dt._queue)
    assert not any(event in ("playlist_done", "done", "error") for event, _ in events)
    # the first item was announced as downloading before the cancel
    announced = [d for e, d in events if e == "playlist_item"]
    assert announced == [{"index": 1, "id": "aaa", "status": "downloading",
                          "position": 1, "total": 2}]


def test_start_playlist_download_spawns_thread_and_schedules_after(tmp_path, monkeypatch):
    release = threading.Event()
    started = threading.Event()
    proc = _BlockingProc([], started, release, rc=0)
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: proc)

    fake_app = _FakeApp()
    c = DownloadController(config=None)
    c.set_app(fake_app)
    c._queue = queue.Queue()
    c._thread = None

    c.start_playlist_download(
        [{"index": 1, "id": "aaa", "url": "https://www.youtube.com/watch?v=aaa"}],
        {"format": "best"},
        tmp_path,
    )
    assert started.wait(timeout=5)
    assert c.is_downloading() is True
    assert any(delay == 100 for delay, _ in fake_app._after_called)
    release.set()
    if c._thread:
        c._thread.join(timeout=1)


def test_poll_queue_dispatches_playlist_item_and_done():
    dt = _bare_controller()
    app = _FakeApp()
    dt._app = app
    received = {"items": [], "done": False}
    dt._callbacks["playlist_item"] = lambda d: received["items"].append(d)
    dt._callbacks["playlist_done"] = lambda: received.update(done=True)

    dt._queue.put(("playlist_item", {"index": 1, "status": "downloading"}))
    dt._queue.put(("playlist_done", None))
    dt._poll_queue()
    assert received["items"] == [{"index": 1, "status": "downloading"}]
    assert received["done"] is True
    assert app._after_called == []


def test_poll_queue_returns_without_rescheduling_after_done():
    dt = _bare_controller()
    app = _FakeApp()
    dt._app = app
    dt._queue.put(("done", None))
    dt._poll_queue()
    assert app._after_called == []


def test_cancel_stop_and_terminates_live_process():
    c = DownloadController(config=None)
    c._queue = queue.Queue()
    fake = _FakeApp()
    c._app = fake
    c._after_id = 99
    proc = _FakeProc(["[info] x"], rc=1)
    c._proc = proc
    c.cancel()
    assert c._stop_event.is_set()
    assert proc.terminated is True
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