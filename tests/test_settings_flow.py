from ui.quality_selector import resolve_initial_selection
from ui.settings_dialog import SettingsDialog
from ui.main_window import MainWindow

import ui.main_window as mw_module


class _StringVarStub:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _FakeConfig:
    def __init__(self, data: dict):
        self._data = data

    def get(self, key, default=None):
        keys = key.split(".")
        obj = self._data
        for k in keys:
            if isinstance(obj, dict):
                obj = obj.get(k)
                if obj is None:
                    return default
            else:
                return default
        return obj

    def set(self, key, value):
        keys = key.split(".")
        obj = self._data
        for k in keys[:-1]:
            obj = obj.setdefault(k, {})
        obj[keys[-1]] = value


# --------------------------------------------------------------------- #
#  Persisted defaults → actual QualitySelector state
# --------------------------------------------------------------------- #


def test_resolve_selection_video_mode_uses_default_quality():
    assert resolve_initial_selection("video", "720p") == ("video", "720p")


def test_resolve_selection_video_mode_falls_back_when_quality_unknown():
    assert resolve_initial_selection("video", "9999p") == ("video", "1080p")


def test_resolve_selection_mp4_only_uses_default_quality():
    assert resolve_initial_selection("mp4_only", "Best") == ("mp4_only", "Best")


def test_resolve_selection_audio_mode_defaults_to_mp3_without_audio_setting():
    # لا إعداد صوت منفصل؛ MP3/M4A محصور في أداة التحكم الرئيسية دائمًا.
    assert resolve_initial_selection("audio", "1080p") == ("audio", "MP3")
    assert resolve_initial_selection("audio", "Best") == ("audio", "MP3")


def test_resolve_selection_invalid_mode_saved_as_video():
    assert resolve_initial_selection("bogus", "360p") == ("video", "360p")


def test_main_window_load_config_state_applies_defaults_to_selector():
    mw = object.__new__(MainWindow)
    mw._dir_var = _StringVarStub()
    applied = {}

    class _Selector:
        def apply_defaults(self, mode, quality):
            applied.update(mode=mode, quality=quality)

    mw._quality_selector = _Selector()
    mw.config = _FakeConfig(
        {
            "download": {"default_dir": "C:\\vids", "default_quality": "720p", "default_mode": "video"},
        }
    )
    mw._load_config_state()
    assert mw._dir_var.get() == "C:\\vids"
    assert applied == {"mode": "video", "quality": "720p"}


# --------------------------------------------------------------------- #
#  Default directory actually lands on disk via _resolve_save_dir
# --------------------------------------------------------------------- #


def test_resolve_save_dir_uses_entry_when_set(tmp_path):
    mw = object.__new__(MainWindow)
    mw._dir_var = _StringVarStub(str(tmp_path / "custom"))
    mw.config = _FakeConfig({"download": {"default_dir": str(tmp_path / "cfg")}})
    assert mw._resolve_save_dir() == tmp_path / "custom"


def test_resolve_save_dir_falls_back_to_config_default(tmp_path):
    mw = object.__new__(MainWindow)
    mw._dir_var = _StringVarStub("")
    mw.config = _FakeConfig({"download": {"default_dir": str(tmp_path / "cfg")}})
    assert mw._resolve_save_dir() == tmp_path / "cfg"
    assert (tmp_path / "cfg").is_dir()


def test_playlist_save_dir_creates_subfolder_named_after_playlist(tmp_path):
    mw = object.__new__(MainWindow)
    mw._current_playlist = {"title": 'Mix: Greatest Hits / 2026'}
    target = mw._playlist_save_dir(tmp_path)
    assert target == tmp_path / "Mix_ Greatest Hits _ 2026"
    assert target.is_dir()


def test_playlist_save_dir_falls_back_when_no_playlist_title(tmp_path):
    mw = object.__new__(MainWindow)
    mw._current_playlist = None
    target = mw._playlist_save_dir(tmp_path)
    assert target == tmp_path / "Playlist"
    assert target.is_dir()


# --------------------------------------------------------------------- #
#  F-A2: closing the window must shut the controller down (no orphans)
# --------------------------------------------------------------------- #


class _FakeShutdownController:
    def __init__(self):
        self.shutdown_calls = 0

    def shutdown(self):
        self.shutdown_calls += 1


class _FakeMaster:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


def test_on_close_saves_dir_and_shuts_down_controller():
    mw = object.__new__(MainWindow)
    mw._dir_var = _StringVarStub("C:\\vids")
    mw._playlist_dir_var = _StringVarStub("")
    mw.config = _FakeConfig({"download": {"default_dir": "C:\\old"}})
    controller = _FakeShutdownController()
    mw._controller = controller
    master = _FakeMaster()
    mw.master = master
    mw._on_close()
    # changed dir persisted, controller released, window destroyed
    assert mw.config.get("download.default_dir") == "C:\\vids"
    assert controller.shutdown_calls == 1
    assert master.destroyed is True


def test_on_close_with_unchanged_dir_shuts_down_controller():
    mw = object.__new__(MainWindow)
    mw._dir_var = _StringVarStub("C:\\same")
    mw._playlist_dir_var = _StringVarStub("")
    mw.config = _FakeConfig({"download": {"default_dir": "C:\\same"}})
    controller = _FakeShutdownController()
    mw._controller = controller
    master = _FakeMaster()
    mw.master = master
    mw._on_close()
    assert controller.shutdown_calls == 1
    assert master.destroyed is True


# --------------------------------------------------------------------- #
#  F-A5: unusable save directory falls back instead of crashing
# --------------------------------------------------------------------- #


class _StubLog:
    def __init__(self):
        self.messages = []

    def append_log(self, msg):
        self.messages.append(msg)


class _FakeMessagebox:
    def __init__(self):
        self.warnings = []

    def showwarning(self, title, message, **kwargs):
        self.warnings.append((title, message))


def test_resolve_dir_falls_back_when_target_is_existing_file(tmp_path, monkeypatch):
    target = tmp_path / "not_a_dir"
    target.write_text("I am a file, not a directory", encoding="utf-8")
    fallback = tmp_path / "fallback_dir"
    monkeypatch.setattr(mw_module, "get_downloads_dir", lambda: fallback)
    box = _FakeMessagebox()
    monkeypatch.setattr(mw_module, "messagebox", box)
    log = _StubLog()
    mw = object.__new__(MainWindow)
    mw._dir_var = _StringVarStub(str(target))
    mw._video_logs = log
    mw.config = _FakeConfig({"download": {"default_dir": str(target)}})

    result = mw._resolve_dir(mw._dir_var, log)
    assert result == fallback
    assert fallback.is_dir()
    assert len(box.warnings) == 1
    assert log.messages and "[ERROR]" in log.messages[0]


def test_resolve_save_dir_uses_fallback_and_warns_for_bad_entry(tmp_path, monkeypatch):
    target = tmp_path / "blocked"
    target.write_text("file", encoding="utf-8")
    fallback = tmp_path / "fb"
    monkeypatch.setattr(mw_module, "get_downloads_dir", lambda: fallback)
    box = _FakeMessagebox()
    monkeypatch.setattr(mw_module, "messagebox", box)
    mw = object.__new__(MainWindow)
    mw._dir_var = _StringVarStub(str(target))
    mw._video_logs = _StubLog()
    mw.config = _FakeConfig({"download": {"default_dir": str(target)}})

    assert mw._resolve_save_dir() == fallback
    assert len(box.warnings) == 1


def test_playlist_save_dir_falls_back_to_base_when_subfolder_is_a_file(tmp_path, monkeypatch):
    sub = tmp_path / "collision"
    sub.write_text("file", encoding="utf-8")
    box = _FakeMessagebox()
    monkeypatch.setattr(mw_module, "messagebox", box)
    mw = object.__new__(MainWindow)
    mw._current_playlist = {"title": "collision"}
    mw._playlist_logs = _StubLog()

    assert mw._playlist_save_dir(tmp_path) == tmp_path
    assert len(box.warnings) == 1


def test_resolve_dir_warns_and_uses_downloads_when_default_bad(tmp_path, monkeypatch):
    # empty entry -> falls back to config default, which is also unusable
    bad = tmp_path / "also_a_file"
    bad.write_text("file", encoding="utf-8")
    fallback = tmp_path / "home_downloads"
    monkeypatch.setattr(mw_module, "get_downloads_dir", lambda: fallback)
    box = _FakeMessagebox()
    monkeypatch.setattr(mw_module, "messagebox", box)
    mw = object.__new__(MainWindow)
    mw._dir_var = _StringVarStub("")
    mw._video_logs = _StubLog()
    mw.config = _FakeConfig({"download": {"default_dir": str(bad)}})

    assert mw._resolve_dir(mw._dir_var, mw._video_logs) == fallback
    assert len(box.warnings) == 1


# --------------------------------------------------------------------- #
#  F-A1: _display_info uses the quality list from the fetch thread
# --------------------------------------------------------------------- #


class _LabelStub:
    def __init__(self):
        self.configs = []

    def configure(self, **kwargs):
        self.configs.append(kwargs)


class _QualityStub:
    def __init__(self):
        self.calls = []

    def set_qualities(self, qualities):
        self.calls.append(list(qualities))


def test_display_info_uses_passed_qualities_without_reextraction():
    mw = object.__new__(MainWindow)
    mw._fetch_btn = _LabelStub()
    mw._title_label = _LabelStub()
    mw._info_label = _LabelStub()
    mw._download_btn = _LabelStub()
    mw._quality_selector = _QualityStub()
    mw._thumb_label = _LabelStub()

    info = {
        "title": "My Video",
        "duration": 125,
        "uploader": "Channel",
        "formats": [{"height": 1080}],
    }
    mw._display_info(info, ["Best", "1080p", "720p"])
    assert mw._quality_selector.calls == [["Best", "1080p", "720p"]]
    assert mw._current_info == info
    # no network fetch, no url-var access -> no re-extraction on the UI thread


def test_display_info_defaults_to_best_when_no_qualities():
    mw = object.__new__(MainWindow)
    mw._fetch_btn = _LabelStub()
    mw._title_label = _LabelStub()
    mw._info_label = _LabelStub()
    mw._download_btn = _LabelStub()
    mw._quality_selector = _QualityStub()
    mw._thumb_label = _LabelStub()

    mw._display_info({"title": "T", "formats": []}, None)
    assert mw._quality_selector.calls == [["Best"]]


def test_parse_int_reads_valid_value():
    var = _StringVarStub("6")
    assert SettingsDialog._parse_int(var, 4, minimum=1, maximum=16) == 6
    assert var.get() == "6"


def test_parse_int_falls_back_on_garbage_and_sanitizes_var():
    var = _StringVarStub("abc")
    assert SettingsDialog._parse_int(var, 4, minimum=1, maximum=16) == 4
    assert var.get() == "4"


def test_parse_int_clamps_out_of_range_back_to_default():
    var = _StringVarStub("999")
    assert SettingsDialog._parse_int(var, 4, minimum=1, maximum=16) == 4
    assert var.get() == "4"

    below = _StringVarStub("-5")
    assert SettingsDialog._parse_int(below, 10, minimum=0, maximum=100) == 10
    assert below.get() == "10"