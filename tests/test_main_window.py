import tkinter as tk
from pathlib import Path

import pytest

import ui.main_window as mw_module
from ui.main_window import MainWindow, _VIDEO_TAB, _PLAYLIST_TAB, _RUN_VIDEO, _RUN_PLAYLIST


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value

    def trace_add(self, *_):
        return None


class _Widget:
    def __init__(self, **initial):
        self.states = dict(initial)

    def configure(self, **kwargs):
        self.states.update(kwargs)

    def cget(self, key):
        return self.states.get(key)


class _LogStub:
    def __init__(self):
        self.messages = []

    def append_log(self, msg):
        self.messages.append(msg)


class _ProgressStub:
    def __init__(self):
        self.calls = []

    def _record(self, name, *args):
        self.calls.append((name,) + args)

    def reset(self):
        self._record("reset")

    def set_done(self):
        self._record("set_done")

    def set_error(self, data):
        self._record("set_error", data)

    def set_message(self, msg):
        self._record("set_message", msg)

    def update_progress(self, d):
        self._record("update_progress", d)


class _PanelStub:
    def __init__(self):
        self.calls = []
        self.to_return = []

    def show(self):
        self.calls.append("show")

    def set_playlist(self, pl):
        self.calls.append(("set_playlist", pl))

    def update_item(self, index, status, error=None):
        self.calls.append(("update_item", index, status, error))

    def begin_download(self, indices=None):
        self.calls.append(("begin_download", indices))

    def finish_download(self):
        self.calls.append("finish_download")

    def selected_entries(self):
        return self.to_return


class _SelectorStub:
    def __init__(self, quality="1080p", mode="video"):
        self.quality = quality
        self.mode = mode
        self.applied = []

    def apply_defaults(self, mode, quality):
        self.applied.append((mode, quality))

    def set_qualities(self, qualities):
        self.qualities = list(qualities)


class _TabViewStub:
    def __init__(self):
        self.active = _VIDEO_TAB
        self.sets = []

    def get(self):
        return self.active

    def set(self, name):
        self.active = name
        self.sets.append(name)


class _ControllerStub:
    def __init__(self):
        self.events = {}
        self.downloading = False
        self.starts = []
        self.playlist_starts = []
        self.cancel_calls = 0
        self.shutdown_calls = 0

    def on(self, event, callback):
        self.events[event] = callback

    def is_downloading(self):
        return self.downloading

    def start_download(self, url, opts, save_dir):
        self.starts.append((url, opts, save_dir))

    def start_playlist_download(self, entries, opts, save_dir):
        self.playlist_starts.append((list(entries), opts, save_dir))

    def cancel(self):
        self.cancel_calls += 1

    def shutdown(self):
        self.shutdown_calls += 1


class _FakeConfig:
    def __init__(self, data):
        self._data = data
        self.sets = []

    def get(self, key, default=None):
        obj = self._data
        for k in key.split("."):
            if isinstance(obj, dict):
                obj = obj.get(k)
                if obj is None:
                    return default
            else:
                return default
        return obj

    def set(self, key, value):
        self.sets.append((key, value))
        obj = self._data
        keys = key.split(".")
        for k in keys[:-1]:
            obj = obj.setdefault(k, {})
        obj[keys[-1]] = value


def _wired_window(**overrides):
    mw = object.__new__(MainWindow)
    mw.config = _FakeConfig({})
    mw._controller = _ControllerStub()
    mw.master = object()
    mw._current_info = None
    mw._current_video_dir = None
    mw._current_playlist_dir = None
    mw._current_playlist = None
    mw._playlist_run = {"completed": 0, "failed": 0, "total": 0}
    mw._active_page = _VIDEO_TAB
    mw._active_run = None

    defaults = {
        "_url_var": _Var(),
        "_dir_var": _Var(),
        "_playlist_url_var": _Var(),
        "_playlist_dir_var": _Var(),
        "_url_entry": _Widget(state="normal"),
        "_fetch_btn": _Widget(text="استعلام", state="normal"),
        "_download_btn": _Widget(state="disabled"),
        "_cancel_btn": _Widget(state="disabled"),
        "_open_folder_btn": _Widget(state="disabled"),
        "_settings_btn": _Widget(),
        "_title_label": _Widget(),
        "_info_label": _Widget(),
        "_thumb_label": _Widget(),
        "_quality_selector": _SelectorStub(),
        "_video_progress": _ProgressStub(),
        "_video_logs": _LogStub(),
        "_playlist_url_entry": _Widget(state="normal"),
        "_playlist_fetch_btn": _Widget(text="استعلام", state="normal"),
        "_playlist_msg_label": _Widget(),
        "_playlist_panel": _PanelStub(),
        "_playlist_quality_selector": _SelectorStub(),
        "_playlist_dir_entry": _Widget(state="normal"),
        "_playlist_download_btn": _Widget(state="disabled"),
        "_playlist_cancel_btn": _Widget(state="disabled"),
        "_playlist_open_folder_btn": _Widget(state="disabled"),
        "_playlist_progress": _ProgressStub(),
        "_playlist_logs": _LogStub(),
        "_status_bar": _Widget(text="جاهز"),
        "_tabview": _TabViewStub(),
        "_thumb_photo": None,
    }
    for name, value in defaults.items():
        setattr(mw, name, value)

    mw._afters = []
    mw.after = lambda ms, fn, *args: mw._afters.append((ms, fn, args))
    mw.wait_window = lambda widget: None

    for name, value in overrides.items():
        setattr(mw, name, value)
    return mw


def _patch_format_opts(monkeypatch, base=None, fmt=None):
    base = base if base is not None else {"paths": {"home": "C:\\results"}}
    fmt = fmt if fmt is not None else {"format": "best"}
    monkeypatch.setattr(mw_module, "get_common_opts", lambda bin_path, config: dict(base))
    monkeypatch.setattr(mw_module, "build_format_opts", lambda quality, mode, config: dict(fmt))
    return dict(base), dict(fmt)


# --------------------------------------------------------------------- #
#  Layout construction
# --------------------------------------------------------------------- #


def test_main_window_constructs_full_ui(tk_root):
    mw = MainWindow(tk_root, _FakeConfig({"download": {"default_dir": "C:\\known"}}))
    try:
        assert mw._tabview.get() == _VIDEO_TAB
        assert mw._download_btn.cget("state") == "disabled"
        assert mw._cancel_btn.cget("state") == "disabled"
        assert mw._playlist_download_btn.cget("state") == "normal"
        assert mw._dir_var.get() == "C:\\known"
        assert mw._playlist_dir_var.get() == "C:\\known"
        assert mw._video_progress is not None
        assert mw._playlist_panel is not None
    finally:
        mw._controller.shutdown()
        mw.destroy()


def test_load_config_state_applies_default_dir_mode_and_quality():
    mw = _wired_window()
    mw.config = _FakeConfig(
        {"download": {"default_dir": "C:\\vids", "default_mode": "mp4_only", "default_quality": "720p"}}
    )
    mw._load_config_state()
    assert mw._dir_var.get() == "C:\\vids"
    assert mw._quality_selector.applied == [("mp4_only", "720p")]


# --------------------------------------------------------------------- #
#  URL bar behaviour
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("valid", [True, False])
def test_on_url_change_toggles_fetch_button(monkeypatch, valid):
    monkeypatch.setattr(mw_module, "is_valid_youtube_url", lambda url: valid)
    mw = _wired_window()
    mw._on_url_change("ignored")
    assert mw._fetch_btn.cget("state") == ("normal" if valid else "disabled")


def test_fetch_info_returns_early_when_url_empty():
    mw = _wired_window()
    mw._fetch_info()
    assert mw._afters == []


def test_fetch_info_routes_playlist_url_to_playlist(monkeypatch):
    monkeypatch.setattr(mw_module, "classify_url", lambda url: "playlist")
    mw = _wired_window()
    routed = []
    mw._route_to_playlist = lambda url: routed.append(url)
    mw._url_var.set("https://www.youtube.com/playlist?list=ABC123")
    mw._fetch_info()
    assert routed == ["https://www.youtube.com/playlist?list=ABC123"]


def test_fetch_info_posts_extracted_info_back_onto_main_thread(monkeypatch):
    class SyncThread:
        def __init__(self, target, daemon=False):
            self._target = target
            self.daemon = daemon

        def start(self):
            self._target()

    monkeypatch.setattr(mw_module, "classify_url", lambda url: "video")
    monkeypatch.setattr(mw_module.threading, "Thread", SyncThread)

    info = {"title": "T", "formats": []}
    monkeypatch.setattr(mw_module, "extract_info", lambda url: info)
    monkeypatch.setattr(mw_module, "qualities_from_info", lambda info: ["Best", "720p"])

    mw = _wired_window()
    mw._url_var.set("https://youtu.be/abc123")
    mw._fetch_info()

    assert mw._fetch_btn.cget("state") == "disabled"
    assert mw._fetch_btn.cget("text") == "جارٍ..."
    assert mw._download_btn.cget("state") == "disabled"
    assert mw._afters == [(0, mw._display_info, (info, ["Best", "720p"]))]


# --------------------------------------------------------------------- #
#  Playlist fetch / routing
# --------------------------------------------------------------------- #


def test_route_to_playlist_switches_tab_and_fetches():
    mw = _wired_window()
    fetched = []
    mw._fetch_playlist = lambda: fetched.append(1)
    mw._route_to_playlist("https://www.youtube.com/playlist?list=XYZ")
    assert mw._playlist_url_var.get() == "https://www.youtube.com/playlist?list=XYZ"
    assert mw._tabview.active == _PLAYLIST_TAB
    assert mw._active_page == _PLAYLIST_TAB
    assert fetched == [1]


def test_fetch_playlist_returns_early_when_url_empty():
    mw = _wired_window()
    mw._fetch_playlist()
    assert mw._afters == []


def test_fetch_playlist_rejects_non_playlist_url(monkeypatch):
    monkeypatch.setattr(mw_module, "classify_url", lambda url: "video")
    mw = _wired_window()
    mw._playlist_url_var.set("https://www.youtube.com/watch?v=abc")
    mw._fetch_playlist()
    assert "ليس قائمة تشغيل" in mw._playlist_msg_label.cget("text")


def test_fetch_playlist_posts_data_back_on_main_thread(monkeypatch):
    class SyncThread:
        def __init__(self, target, daemon=False):
            self._target = target
            self.daemon = daemon

        def start(self):
            self._target()

    monkeypatch.setattr(mw_module.threading, "Thread", SyncThread)
    monkeypatch.setattr(mw_module, "classify_url", lambda url: "playlist")
    data = {"title": "Mix", "entries": [{"title": "A"}]}
    monkeypatch.setattr(mw_module, "extract_playlist", lambda url: data)
    mw = _wired_window()
    mw._playlist_url_var.set("https://www.youtube.com/playlist?list=XYZ")
    mw._fetch_playlist()
    assert mw._playlist_fetch_btn.cget("state") == "disabled"
    assert ("set_playlist", {"entries": []}) in mw._playlist_panel.calls
    assert mw._afters == [(0, mw._display_playlist, (data,))]


def test_display_playlist_failure_message_when_no_entries():
    mw = _wired_window()
    mw._display_playlist({"entries": []})
    assert "فشل استخراج القائمة" in mw._playlist_msg_label.cget("text")
    assert mw._playlist_download_btn.cget("state") == "disabled"


def test_display_playlist_populates_panel_and_enables_download():
    mw = _wired_window()
    playlist = {"title": "Mix", "entries": [{"title": "A"}, {"title": "B"}]}
    mw._display_playlist(playlist)
    assert mw._current_playlist == playlist
    assert mw._playlist_msg_label.cget("text") == ""
    assert ("set_playlist", playlist) in mw._playlist_panel.calls
    assert "show" in mw._playlist_panel.calls
    assert mw._playlist_download_btn.cget("state") == "normal"


def test_on_tab_changed_syncs_playlist_panel_on_playlist_tab():
    mw = _wired_window()
    mw._tabview.active = _PLAYLIST_TAB
    mw._on_tab_changed()
    assert mw._active_page == _PLAYLIST_TAB
    assert "show" in mw._playlist_panel.calls


# --------------------------------------------------------------------- #
#  Display info / thumbnail
# --------------------------------------------------------------------- #


def test_display_info_failure_shows_error_and_keeps_download_disabled():
    mw = _wired_window()
    mw._display_info(None, None)
    assert "فشل استخراج المعلومات" in mw._title_label.cget("text")
    assert mw._download_btn.cget("state") == "disabled"
    assert mw._fetch_btn.cget("text") == "استعلام"


def test_display_info_sets_metadata_qualities_and_fetches_thumb(monkeypatch):
    mw = _wired_window()
    thumb_loaded = []
    monkeypatch.setattr(mw_module, "extract_title", lambda info: "Hello")
    monkeypatch.setattr(mw_module, "extract_duration", lambda info: 125)
    monkeypatch.setattr(mw_module, "extract_uploader", lambda info: "Channel")
    monkeypatch.setattr(mw_module, "extract_thumbnail", lambda info: "http://img/a.jpg")
    mw._load_thumbnail = lambda url: thumb_loaded.append(url)

    info = {"title": "Hello"}
    mw._display_info(info, ["Best", "1080p"])

    assert mw._current_info == info
    assert mw._title_label.cget("text") == "🎬 Hello"
    assert "القناة: Channel" in mw._info_label.cget("text")
    assert "2:05" in mw._info_label.cget("text")
    assert mw._quality_selector.qualities == ["Best", "1080p"]
    assert thumb_loaded == ["http://img/a.jpg"]
    assert mw._download_btn.cget("state") == "normal"


def test_load_thumbnail_applies_image_successfully(monkeypatch):
    class FakeResp:
        content = b"fake-image-bytes"

        def raise_for_status(self):
            return None

    class FakeImage:
        def resize(self, size, resample):
            return self

    class FakePhoto:
        pass

    monkeypatch.setattr(mw_module.requests, "get", lambda url, timeout=10: FakeResp())
    monkeypatch.setattr(mw_module.Image, "open", lambda buf: FakeImage())
    monkeypatch.setattr(mw_module.ctk, "CTkImage", lambda img, size: FakePhoto())

    class SyncThread:
        def __init__(self, target, daemon=False):
            self._target = target
            self.daemon = daemon

        def start(self):
            self._target()

    monkeypatch.setattr(mw_module.threading, "Thread", SyncThread)

    mw = _wired_window()
    mw._load_thumbnail("http://img/a.jpg")
    assert len(mw._afters) == 1
    _, fn, args = mw._afters[0]
    assert args == ()
    fn()
    assert mw._thumb_label.cget("image") is not None
    assert mw._thumb_photo is not None


def test_load_thumbnail_swallows_tcl_error_apply(monkeypatch):
    class FakeResp:
        content = b"x"

        def raise_for_status(self):
            return None

    class FakeImage:
        def resize(self, size, resample):
            return self

    class FakePhoto:
        pass

    class ErroringLabel:
        def configure(self, **kwargs):
            raise tk.TclError("dead widget")

    monkeypatch.setattr(mw_module.requests, "get", lambda url, timeout=10: FakeResp())
    monkeypatch.setattr(mw_module.Image, "open", lambda buf: FakeImage())
    monkeypatch.setattr(mw_module.ctk, "CTkImage", lambda img, size: FakePhoto())

    class SyncThread:
        def __init__(self, target, daemon=False):
            self._target = target
            self.daemon = daemon

        def start(self):
            self._target()

    monkeypatch.setattr(mw_module.threading, "Thread", SyncThread)

    mw = _wired_window(_thumb_label=ErroringLabel())
    mw._load_thumbnail("http://img/a.jpg")
    _, fn, _ = mw._afters[0]
    fn()


def test_load_thumbnail_logs_request_error(monkeypatch, caplog):
    class SyncThread:
        def __init__(self, target, daemon=False):
            self._target = target
            self.daemon = daemon

        def start(self):
            self._target()

    monkeypatch.setattr(mw_module.threading, "Thread", SyncThread)
    monkeypatch.setattr(mw_module.requests, "get", lambda url, timeout=10: (_ for _ in ()).throw(
        mw_module.requests.RequestException("boom")
    ))
    mw = _wired_window()
    with caplog.at_level("DEBUG", logger="ui.main_window"):
        mw._load_thumbnail("http://img/a.jpg")
    assert mw._afters == []
    assert "Could not load thumbnail" in caplog.text


# --------------------------------------------------------------------- #
#  Download options
# --------------------------------------------------------------------- #


def test_build_download_opts_no_cookies(monkeypatch):
    _patch_format_opts(monkeypatch)
    mw = _wired_window()
    opts, quality, mode = mw._build_download_opts()
    assert quality == "1080p"
    assert mode == "video"
    assert "cookiesfrombrowser" not in opts
    assert "cookiefile" not in opts


def test_build_download_opts_browser_cookies(monkeypatch):
    _patch_format_opts(monkeypatch)
    mw = _wired_window()
    mw.config = _FakeConfig({"cookies": {"source": "browser", "browser": "firefox"}})
    opts, _, _ = mw._build_download_opts()
    assert opts["cookiesfrombrowser"] == ("firefox",)


def test_build_download_opts_cookie_file_when_present(monkeypatch, tmp_path):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("cookie", encoding="utf-8")
    _patch_format_opts(monkeypatch)
    mw = _wired_window()
    mw.config = _FakeConfig({"cookies": {"source": "file", "file_path": str(cookie_file)}})
    opts, _, _ = mw._build_download_opts()
    assert opts["cookiefile"] == str(cookie_file)


def test_build_download_opts_cookie_file_skipped_when_missing(monkeypatch, tmp_path):
    _patch_format_opts(monkeypatch)
    monkeypatch.setattr(mw_module, "cookies_path", lambda: tmp_path / "missing.txt")
    mw = _wired_window()
    mw.config = _FakeConfig({"cookies": {"source": "file", "file_path": "relative.txt"}})
    opts, _, _ = mw._build_download_opts()
    assert "cookiefile" not in opts


def test_build_download_opts_sponsorblock(monkeypatch):
    _patch_format_opts(monkeypatch)
    mw = _wired_window()
    mw.config = _FakeConfig({
        "advanced": {"sponsorblock_remove": True, "sponsorblock_categories": ["sponsor", "intro"]}
    })
    opts, _, _ = mw._build_download_opts()
    assert opts["sponsorblock_remove"] == ["sponsor", "intro"]


# --------------------------------------------------------------------- #
#  Start / cancel downloads
# --------------------------------------------------------------------- #


def test_start_download_guard_when_already_downloading():
    mw = _wired_window()
    mw._controller.downloading = True
    mw._url_var.set("https://www.youtube.com/watch?v=abc")
    mw._start_download()
    assert mw._controller.starts == []
    assert any("يوجد تحميل جارٍ" in msg for msg in mw._video_logs.messages)


def test_start_download_empty_url_is_noop():
    mw = _wired_window()
    mw._start_download()
    assert mw._controller.starts == []


def test_start_download_flow(monkeypatch, tmp_path):
    _patch_format_opts(monkeypatch)
    mw = _wired_window()
    url = "https://www.youtube.com/watch?v=abc&list=PLxyz"
    mw._url_var.set(url)
    mw._dir_var.set(str(tmp_path / "out"))
    ctl = mw._controller
    mw._start_download()

    assert ctl.starts
    start_url, opts, save_dir = ctl.starts[0]
    assert start_url == url
    assert save_dir == tmp_path / "out"
    assert opts["format"] == "best"
    assert mw._active_run == _RUN_VIDEO
    assert mw._current_video_dir == tmp_path / "out"
    assert any("بدء التحميل" in msg for msg in mw._video_logs.messages)
    assert any("semantics قائمة تشغيل" not in msg for msg in mw._video_logs.messages)
    assert any("قائمة تشغيل — سيتم تنزيل الفيديو فقط" in msg for msg in mw._video_logs.messages)
    assert mw._download_btn.cget("state") == "disabled"
    assert mw._cancel_btn.cget("state") == "normal"
    assert mw._fetch_btn.cget("state") == "disabled"
    assert mw._url_entry.cget("state") == "disabled"
    assert mw._open_folder_btn.cget("state") == "disabled"


def test_start_playlist_download_all_empty_without_current_playlist():
    mw = _wired_window()
    mw._current_playlist = None
    mw._start_playlist_download_all()
    assert any("لا توجد مقاطع محددة" in msg for msg in mw._playlist_logs.messages)


def test_start_playlist_download_guard_when_already_downloading():
    mw = _wired_window()
    mw._controller.downloading = True
    mw._start_playlist_download([{"title": "A"}])
    assert mw._controller.playlist_starts == []


def test_start_playlist_download_flow(monkeypatch, tmp_path):
    _patch_format_opts(monkeypatch)
    mw = _wired_window(_current_playlist={"title": "My Mix", "entries": [{"title": "A"}, {"title": "B"}]})
    entries = [{"title": "A", "index": 1}, {"title": "B", "index": 2}]
    mw._playlist_dir_var.set(str(tmp_path / "base"))
    ctl = mw._controller
    mw._start_playlist_download(entries)

    assert ctl.playlist_starts
    start_entries, opts, save_dir = ctl.playlist_starts[0]
    assert start_entries == entries
    assert save_dir == tmp_path / "base" / "My Mix"
    assert mw._active_run == _RUN_PLAYLIST
    assert mw._playlist_run["total"] == 2
    assert ("begin_download", [1, 2]) in mw._playlist_panel.calls
    assert mw._playlist_download_btn.cget("state") == "disabled"
    assert mw._playlist_cancel_btn.cget("state") == "normal"
    assert mw._playlist_url_entry.cget("state") == "disabled"
    assert mw._playlist_open_folder_btn.cget("state") == "normal"


def test_cancel_download_video_run():
    mw = _wired_window()
    mw._active_run = _RUN_VIDEO
    mw._cancel_download()
    assert mw._controller.cancel_calls == 1
    assert mw._active_run is None
    assert "[INFO] تم إلغاء التحميل" in mw._video_logs.messages
    assert ("reset",) in mw._video_progress.calls
    assert mw._cancel_btn.cget("state") == "disabled"
    assert mw._download_btn.cget("state") == "normal"


def test_cancel_download_playlist_run():
    mw = _wired_window()
    mw._active_run = _RUN_PLAYLIST
    mw._playlist_run = {"completed": 1, "failed": 1, "total": 2}
    mw._cancel_download()
    assert mw._controller.cancel_calls == 1
    assert mw._active_run is None
    assert "[INFO] تم إلغاء التحميل" in mw._playlist_logs.messages
    assert ("reset",) in mw._playlist_progress.calls
    assert "finish_download" in mw._playlist_panel.calls
    assert mw._playlist_run == {"completed": 0, "failed": 0, "total": 0}


# --------------------------------------------------------------------- #
#  Folders / settings
# --------------------------------------------------------------------- #


def test_open_folder_uses_current_video_dir(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(mw_module, "open_folder", lambda path: opened.append(path))
    mw = _wired_window(_current_video_dir=tmp_path)
    mw._open_folder()
    assert opened == [tmp_path]


def test_open_folder_missing_dir_is_noop(monkeypatch):
    called = []
    monkeypatch.setattr(mw_module, "open_folder", lambda path: called.append(path))
    mw = _wired_window(_current_video_dir=Path("Q:/does_not_exist_xyz"))
    mw._open_folder()
    assert called == []


def test_open_playlist_folder_uses_current_playlist_dir(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(mw_module, "open_folder", lambda path: opened.append(path))
    mw = _wired_window(_current_playlist_dir=tmp_path)
    mw._open_playlist_folder()
    assert opened == [tmp_path]


def test_browse_dir_sets_var_and_config(monkeypatch):
    monkeypatch.setattr(mw_module.fd, "askdirectory", lambda **kwargs: "C:\\picked")
    mw = _wired_window()
    mw._dir_var.set("C:\\old")
    mw._browse_dir(mw._dir_var)
    assert mw._dir_var.get() == "C:\\picked"
    assert mw.config.get("download.default_dir") == "C:\\picked"


def test_browse_dir_cancelled_keeps_values(monkeypatch):
    monkeypatch.setattr(mw_module.fd, "askdirectory", lambda **kwargs: "")
    mw = _wired_window()
    mw._browse_dir(mw._dir_var)
    assert mw._dir_var.get() == ""
    assert mw.config.get("download.default_dir") is None


def test_open_settings_syncs_default_dir_after_dialog(monkeypatch):
    class FakeDialog:
        def __init__(self, master, config):
            self.destroy = lambda: None

    monkeypatch.setattr(mw_module, "SettingsDialog", FakeDialog)
    mw = _wired_window()
    mw.config = _FakeConfig({"download": {"default_dir": "C:\\saved"}})
    mw._dir_var.set("C:\\old")
    mw._playlist_dir_var.set("")
    mw._open_settings()
    assert mw._dir_var.get() == "C:\\old"
    assert mw._playlist_dir_var.get() == "C:\\old"
    assert mw.config.get("download.default_dir") == "C:\\old"


# --------------------------------------------------------------------- #
#  Controller event wiring
# --------------------------------------------------------------------- #


def test_setup_callbacks_registers_all_events():
    mw = _wired_window()
    mw._setup_callbacks()
    assert set(mw._controller.events) == {
        "progress", "done", "error", "log", "playlist_item", "playlist_done"
    }


def test_progress_callback_updates_active_page():
    mw = _wired_window(_active_run=_RUN_VIDEO)
    mw._setup_callbacks()
    d = {"status": "downloading", "downloaded_bytes": 5, "total_bytes": 10}
    mw._controller.events["progress"](d)
    assert mw._video_progress.calls[-1] == ("update_progress", d)


def test_progress_callback_ignored_when_no_active_run():
    mw = _wired_window(_active_run=None)
    mw._setup_callbacks()
    mw._controller.events["progress"]({"status": "downloading"})
    assert mw._video_progress.calls == []
    assert mw._playlist_progress.calls == []


def test_done_callback_video_run():
    mw = _wired_window(_active_run=_RUN_VIDEO)
    mw._setup_callbacks()
    mw._controller.events["done"]()
    assert mw._active_run is None
    assert ("set_done",) in mw._video_progress.calls
    assert "[INFO] اكتمل التحميل بنجاح" in mw._video_logs.messages
    assert mw._download_btn.cget("state") == "normal"
    assert mw._cancel_btn.cget("state") == "disabled"


def test_done_callback_playlist_run():
    mw = _wired_window(_active_run=_RUN_PLAYLIST)
    mw._setup_callbacks()
    mw._controller.events["done"]()
    assert mw._active_run is None
    assert ("set_done",) in mw._playlist_progress.calls
    assert mw._playlist_download_btn.cget("state") == "normal"
    assert mw._playlist_cancel_btn.cget("state") == "disabled"


def test_error_callback_uses_active_page():
    mw = _wired_window(_active_run=_RUN_VIDEO)
    mw._setup_callbacks()
    mw._controller.events["error"]("unavailable")
    assert ("set_error", "unavailable") in mw._video_progress.calls
    assert "[ERROR] unavailable" in mw._video_logs.messages
    assert mw._active_run is None


def test_log_callback_appends_to_active_page():
    mw = _wired_window(_active_run=_RUN_VIDEO)
    mw._setup_callbacks()
    mw._controller.events["log"]("[info] x")
    assert "[info] x" in mw._video_logs.messages


def test_log_callback_ignored_when_no_active_run():
    mw = _wired_window(_active_run=None)
    mw._setup_callbacks()
    mw._controller.events["log"]("stray message")
    assert mw._video_logs.messages == []
    assert mw._playlist_logs.messages == []


def test_error_callback_playlist_run_restores_playlist_ui():
    mw = _wired_window(_active_run=_RUN_PLAYLIST)
    mw._setup_callbacks()
    mw._controller.events["error"]("media blocked")
    assert ("set_error", "media blocked") in mw._playlist_progress.calls
    assert "[ERROR] media blocked" in mw._playlist_logs.messages
    assert mw._active_run is None
    assert mw._playlist_download_btn.cget("state") == "normal"
    assert mw._playlist_cancel_btn.cget("state") == "disabled"


def test_playlist_item_downloading_updates_progress_message():
    mw = _wired_window(_active_run=_RUN_PLAYLIST)
    mw._setup_callbacks()
    mw._controller.events["playlist_item"](
        {"index": 2, "status": "downloading", "position": 2, "total": 5}
    )
    assert mw._playlist_run["total"] == 5
    assert ("reset",) in mw._playlist_progress.calls
    assert ("set_message", "الفيديو 2 من 5 — جارٍ التنزيل…") in mw._playlist_progress.calls


def test_playlist_item_completed_and_failed_increment_counters():
    mw = _wired_window(_active_run=_RUN_PLAYLIST)
    mw._setup_callbacks()
    mw._controller.events["playlist_item"]({"index": 1, "status": "completed"})
    mw._controller.events["playlist_item"]({"index": 2, "status": "failed", "error": "nope"})
    assert mw._playlist_run["completed"] == 1
    assert mw._playlist_run["failed"] == 1
    assert any("الفيديو 1 تم بنجاح" in m for m in mw._playlist_logs.messages)
    assert any("الفيديو 2 فشل — nope" in m for m in mw._playlist_logs.messages)


def test_playlist_item_failed_without_error_uses_default_text():
    mw = _wired_window(_active_run=_RUN_PLAYLIST)
    mw._setup_callbacks()
    mw._controller.events["playlist_item"]({"index": 3, "status": "failed"})
    assert any("الفيديو 3 فشل — خطأ" in m for m in mw._playlist_logs.messages)


def test_playlist_done_callback_summarises_and_restores():
    mw = _wired_window(_active_run=_RUN_PLAYLIST)
    mw._playlist_run = {"completed": 3, "failed": 1, "total": 4}
    mw._setup_callbacks()
    mw._controller.events["playlist_done"]()
    assert ("set_done",) in mw._playlist_progress.calls
    assert ("set_message", "اكتملت القائمة ✓ — نجح 3 / فشل 1 (من 4)") in mw._playlist_progress.calls
    assert "finish_download" in mw._playlist_panel.calls
    assert mw._active_run is None
    assert mw._playlist_run == {"completed": 0, "failed": 0, "total": 0}
    assert mw._playlist_download_btn.cget("state") == "normal"


# --------------------------------------------------------------------- #
#  UI state helpers
# --------------------------------------------------------------------- #


def test_page_widgets_maps_runs():
    mw = _wired_window()
    assert mw._page_widgets(_RUN_VIDEO) == (mw._video_progress, mw._video_logs)
    assert mw._page_widgets(_RUN_PLAYLIST) == (mw._playlist_progress, mw._playlist_logs)
    assert mw._page_widgets("anything") == (mw._playlist_progress, mw._playlist_logs)


def test_prepare_and_restore_video_ui():
    mw = _wired_window()
    mw._prepare_video_ui()
    assert mw._download_btn.cget("state") == "disabled"
    assert mw._cancel_btn.cget("state") == "normal"
    assert mw._fetch_btn.cget("state") == "disabled"
    assert mw._url_entry.cget("state") == "disabled"
    mw._restore_video_ui()
    assert mw._download_btn.cget("state") == "normal"
    assert mw._cancel_btn.cget("state") == "disabled"
    assert mw._fetch_btn.cget("state") == "normal"
    assert mw._url_entry.cget("state") == "normal"


def test_prepare_and_restore_playlist_ui():
    mw = _wired_window()
    mw._prepare_playlist_ui()
    assert mw._playlist_download_btn.cget("state") == "disabled"
    assert mw._playlist_cancel_btn.cget("state") == "normal"
    assert mw._playlist_fetch_btn.cget("state") == "disabled"
    mw._restore_playlist_ui()
    assert mw._playlist_download_btn.cget("state") == "normal"
    assert mw._playlist_cancel_btn.cget("state") == "disabled"
    assert mw._playlist_fetch_btn.cget("state") == "normal"


def test_fallback_save_dir_returns_downloads(monkeypatch, tmp_path):
    fb = tmp_path / "downloads"
    monkeypatch.setattr(mw_module, "get_downloads_dir", lambda: fb)
    mw = _wired_window()
    assert mw._fallback_save_dir() == fb
    assert fb.is_dir()


def test_fallback_save_dir_returns_path_when_ensure_dir_fails(monkeypatch, tmp_path):
    fb = tmp_path / "downloads"
    monkeypatch.setattr(mw_module, "get_downloads_dir", lambda: fb)
    monkeypatch.setattr(mw_module, "ensure_dir", lambda path: (_ for _ in ()).throw(OSError("denied")))
    mw = _wired_window()
    assert mw._fallback_save_dir() == fb


def test_resolve_dir_falls_back_to_config_default(monkeypatch, tmp_path):
    out = tmp_path / "cfg"
    monkeypatch.setattr(mw_module, "ensure_dir", lambda path: path)
    monkeypatch.setattr(mw_module, "get_downloads_dir", lambda: tmp_path / "dl")
    mw = _wired_window()
    mw.config = _FakeConfig({"download": {"default_dir": str(out)}})
    mw._dir_var.set("")
    assert mw._resolve_dir(mw._dir_var) == out


def test_persist_dir_saves_typed_path_when_differs():
    mw = _wired_window()
    mw.config = _FakeConfig({"download": {"default_dir": "C:\\saved"}})
    mw._dir_var.set("C:\\typed")
    mw._persist_dir(mw._dir_var)
    assert mw.config.get("download.default_dir") == "C:\\typed"


def test_persist_dir_skips_save_when_empty_or_unchanged():
    mw = _wired_window()
    mw.config = _FakeConfig({"download": {"default_dir": "C:\\saved"}})
    mw._dir_var.set("C:\\saved")
    mw._persist_dir(mw._dir_var)
    mw._dir_var.set("  ")
    mw._persist_dir(mw._dir_var)
    mw._playlist_dir_var.set("C:\\saved")
    mw._persist_dir(mw._playlist_dir_var)
    assert mw.config.sets == []
    assert mw.config.get("download.default_dir") == "C:\\saved"


def test_resolve_dir_persists_typed_dir_at_download_time(monkeypatch, tmp_path):
    out = tmp_path / "selected"
    monkeypatch.setattr(mw_module, "ensure_dir", lambda path: path)
    monkeypatch.setattr(mw_module, "get_downloads_dir", lambda: tmp_path / "dl")
    mw = _wired_window()
    mw.config = _FakeConfig({"download": {"default_dir": "C:\\saved"}})
    mw._dir_var.set(str(out))
    assert mw._resolve_dir(mw._dir_var) == out
    assert mw.config.get("download.default_dir") == str(out)


def test_resolve_dir_warns_and_uses_downloads_fallback(monkeypatch, tmp_path):
    fb = tmp_path / "dl"
    shown = []
    monkeypatch.setattr(mw_module, "ensure_dir", lambda path: (_ for _ in ()).throw(OSError("locked")))
    monkeypatch.setattr(mw_module, "get_downloads_dir", lambda: fb)
    monkeypatch.setattr(mw_module.messagebox, "showwarning", lambda *a, **k: shown.append(a))
    mw = _wired_window()
    mw._dir_var.set("D:\\blocked")
    result = mw._resolve_dir(mw._dir_var, mw._video_logs)
    assert result == fb
    assert shown
    assert any("تعذّر إنشاء مجلد الحفظ" in m for m in mw._video_logs.messages)


def test_playlist_save_dir_uses_base_on_error(monkeypatch, tmp_path):
    base = tmp_path / "base"
    shown = []
    monkeypatch.setattr(mw_module, "ensure_dir", lambda path: (_ for _ in ()).throw(OSError("x")))
    monkeypatch.setattr(mw_module.messagebox, "showwarning", lambda *a, **k: shown.append(a))
    mw = _wired_window(_current_playlist={"title": "My Mix"})
    assert mw._playlist_save_dir(base) == base
    assert shown
    assert any("تعذّر إنشاء مجلد القائمة" in m for m in mw._playlist_logs.messages)


def test_on_close_saves_dir_and_destroys_master():
    class FakeMaster:
        def __init__(self):
            self.destroyed = False

        def destroy(self):
            self.destroyed = True

    master = FakeMaster()
    mw = _wired_window()
    mw.master = master
    mw.config = _FakeConfig({"download": {"default_dir": "C:\\saved"}})
    mw._dir_var.set("C:\\new")
    mw._playlist_dir_var.set("")
    mw._on_close()
    assert mw.config.get("download.default_dir") == "C:\\new"
    assert mw._controller.shutdown_calls == 1
    assert master.destroyed


def test_on_close_does_not_revert_persisted_dir_when_both_vars_exist():
    class FakeMaster:
        def destroy(self):
            pass

    mw = _wired_window()
    mw.master = FakeMaster()
    mw.config = _FakeConfig({"download": {"default_dir": "C:\\initial"}})
    mw._dir_var.set("C:\\initial")
    mw._playlist_dir_var.set("C:\\initial")

    # User changes directory from video UI and it persists
    mw._dir_var.set("C:\\new_folder")
    mw._persist_dir(mw._dir_var)
    assert mw.config.get("download.default_dir") == "C:\\new_folder"
    assert mw._playlist_dir_var.get() == "C:\\new_folder"

    # Closing with 'X' must keep the new folder and NOT revert to C:\initial
    mw._on_close()
    assert mw.config.get("download.default_dir") == "C:\\new_folder"


def test_on_close_does_not_revert_persisted_playlist_dir():
    class FakeMaster:
        def destroy(self):
            pass

    mw = _wired_window()
    mw.master = FakeMaster()
    mw.config = _FakeConfig({"download": {"default_dir": "C:\\initial"}})
    mw._dir_var.set("C:\\initial")
    mw._playlist_dir_var.set("C:\\initial")
    mw._active_page = _PLAYLIST_TAB

    mw._playlist_dir_var.set("C:\\playlist_folder")
    mw._persist_dir(mw._playlist_dir_var)
    assert mw.config.get("download.default_dir") == "C:\\playlist_folder"
    assert mw._dir_var.get() == "C:\\playlist_folder"

    mw._on_close()
    assert mw.config.get("download.default_dir") == "C:\\playlist_folder"


def test_on_close_persists_uncommitted_typed_dir_on_active_tab():
    class FakeMaster:
        def destroy(self):
            pass

    mw = _wired_window()
    mw.master = FakeMaster()
    mw.config = _FakeConfig({"download": {"default_dir": "C:\\initial"}})
    mw._dir_var.set("C:\\typed_folder")
    mw._playlist_dir_var.set("C:\\initial")
    mw._active_page = _VIDEO_TAB

    mw._on_close()
    assert mw.config.get("download.default_dir") == "C:\\typed_folder"


def test_tab_changed_syncs_uncommitted_dir():
    class FakeTabview:
        def __init__(self, active):
            self._active = active

        def get(self):
            return self._active

    mw = _wired_window()
    mw.config = _FakeConfig({"download": {"default_dir": "C:\\initial"}})
    mw._tabview = FakeTabview(_PLAYLIST_TAB)
    mw._active_page = _VIDEO_TAB
    mw._dir_var.set("C:\\typed_video")
    mw._playlist_dir_var.set("C:\\initial")

    mw._on_tab_changed()
    assert mw._playlist_dir_var.get() == "C:\\typed_video"
    assert mw.config.get("download.default_dir") == "C:\\typed_video"