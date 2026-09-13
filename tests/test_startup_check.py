from unittest.mock import MagicMock

import pytest

from core.dep_checker import DepResult
from ui.startup_check import StartupCheckFrame


@pytest.fixture
def frame(tk_root, monkeypatch):
    # Prevent automatic background probe during initial widget construction
    monkeypatch.setattr(StartupCheckFrame, "_run_checks", lambda self: None)
    done_cb = MagicMock()
    f = StartupCheckFrame(tk_root, on_done=done_cb)
    f.on_done_mock = done_cb
    return f


def test_display_results_all_dependencies_found_enables_continue_without_warning(frame):
    results = [
        DepResult(name="FFmpeg", found=True, path="bin/ffmpeg.exe", version="6.0", required=True),
        DepResult(name="FFprobe", found=True, path="bin/ffprobe.exe", version="6.0", required=True),
        DepResult(name="yt-dlp", found=True, path="bin/yt-dlp.exe", version="2026.01.01", required=True),
    ]

    frame._display_results(results)

    assert frame._continue_btn.cget("state") == "normal"
    labels = [w.cget("text") for w in frame._status_frame.winfo_children()]
    assert len(labels) == 3
    assert all("✅" in text for text in labels)
    assert not any("مفقودة" in text for text in labels)


def test_display_results_missing_required_dependency_adds_warning_message(frame):
    results = [
        DepResult(name="FFmpeg", found=False, path=None, version=None, required=True),
        DepResult(name="yt-dlp", found=True, path="bin/yt-dlp.exe", version="2026.01.01", required=True),
    ]

    frame._display_results(results)

    assert frame._continue_btn.cget("state") == "normal"
    labels = [w.cget("text") for w in frame._status_frame.winfo_children()]
    assert any("❌" in text and "FFmpeg" in text for text in labels)
    assert any("بعض المكونات الأساسية مفقودة" in text for text in labels)


def test_display_results_missing_optional_dependency_marks_warning_icon(frame):
    results = [
        DepResult(name="FFmpeg", found=True, path="bin/ffmpeg.exe", version="6.0", required=True),
        DepResult(name="Node.js", found=False, path=None, version=None, required=False),
    ]

    frame._display_results(results)

    assert frame._continue_btn.cget("state") == "normal"
    labels = [w.cget("text") for w in frame._status_frame.winfo_children()]
    assert any("⚠️" in text and "Node.js" in text for text in labels)
    assert not any("بعض المكونات الأساسية مفقودة" in text for text in labels)


def test_on_continue_disables_button_and_invokes_done_callback(frame, monkeypatch):
    destroyed = []
    monkeypatch.setattr(frame, "destroy", lambda: destroyed.append(1))
    frame._continue_btn.configure(state="normal")
    frame._on_continue()

    assert frame.on_done_mock.call_count == 1
    assert frame._continue_btn.cget("state") == "disabled"
    assert destroyed == [1]


def test_display_results_clears_previous_children(frame):
    all_found = [
        DepResult(name="FFmpeg", found=True, path="bin/ffmpeg.exe", version="6.0", required=True),
        DepResult(name="Node.js", found=True, path="bin/node.exe", version="v22", required=False),
        DepResult(name="yt-dlp", found=True, path="bin/yt-dlp.exe", version="2026.01.01", required=True),
    ]
    frame._display_results(all_found)
    first_batch = list(frame._status_frame.winfo_children())
    assert len(first_batch) == 3

    frame._display_results([all_found[0]])
    second_batch = list(frame._status_frame.winfo_children())
    assert len(second_batch) == 1
    assert all(w not in second_batch for w in first_batch)


def test_run_checks_posts_results_via_after(monkeypatch):
    import ui.startup_check as sk

    results = [
        DepResult(name="FFmpeg", found=True, path="bin/ffmpeg.exe", version="6.0", required=True),
    ]

    class SyncThread:
        def __init__(self, target, daemon=False):
            self._target = target
            self.daemon = daemon

        def start(self):
            self._target()

    class FakeChecker:
        def check_all(self):
            return results

    monkeypatch.setattr(sk.threading, "Thread", SyncThread)
    monkeypatch.setattr(sk, "DependencyChecker", FakeChecker)
    monkeypatch.setattr(
        sk.ctk,
        "CTkLabel",
        lambda master, **kwargs: _install_label(master, kwargs),
    )

    def make_frame():
        f = object.__new__(StartupCheckFrame)
        f._on_done = lambda: None
        f._status_frame = _StubStatusFrame()
        f._continue_btn = _StubButton()
        return f

    frame = make_frame()
    scheduled = []
    frame.after = lambda ms, fn: scheduled.append((ms, fn))
    updates = []
    frame.update = lambda: updates.append(1)

    frame._run_checks()

    assert updates == [1]
    assert len(scheduled) == 1
    ms, fn = scheduled[0]
    assert ms == 0
    fn()
    assert [w.kwargs["text"] for w in frame._status_frame.children] == ["✅  FFmpeg  6.0"]
    assert frame._continue_btn.state == "normal"


def test_run_checks_swallows_runtime_error_when_frame_destroyed(monkeypatch):
    import ui.startup_check as sk

    class SyncThread:
        def __init__(self, target, daemon=False):
            self._target = target
            self.daemon = daemon

        def start(self):
            self._target()

    class FakeChecker:
        def check_all(self):
            return [DepResult(name="FFmpeg", found=True, path="bin/ffmpeg.exe", version="6.0", required=True)]

    monkeypatch.setattr(sk.threading, "Thread", SyncThread)
    monkeypatch.setattr(sk, "DependencyChecker", FakeChecker)
    monkeypatch.setattr(
        sk.ctk,
        "CTkLabel",
        lambda master, **kwargs: _install_label(master, kwargs),
    )

    frame = object.__new__(StartupCheckFrame)
    frame._on_done = lambda: None
    frame._status_frame = _StubStatusFrame()
    frame._continue_btn = _StubButton()
    frame.after = lambda ms, fn: (_ for _ in ()).throw(RuntimeError("frame destroyed"))
    frame.update = lambda: None

    frame._run_checks()


class _StubStatusFrame:
    def __init__(self):
        self.children = []
        self._destroyed = []

    def winfo_children(self):
        return list(self.children)

    def destroy_label(self, widget):
        self._destroyed.append(widget)
        self.children.remove(widget)


def _install_label(master, kwargs):
    label = _StubLabel(master, kwargs)
    if hasattr(master, "children"):
        master.children.append(label)
    return label


class _StubLabel:
    def __init__(self, master, kwargs):
        self.master = master
        self.kwargs = kwargs

    def pack(self, **kwargs):
        self.packed = kwargs

    def destroy(self):
        if self.master is not None and self in self.master.children:
            self.master.children.remove(self)


class _StubButton:
    def __init__(self):
        self.state = "disabled"

    def configure(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
