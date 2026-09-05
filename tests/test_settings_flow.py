from ui.quality_selector import resolve_initial_selection
from ui.settings_dialog import SettingsDialog
from ui.main_window import MainWindow


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
#  Settings dialog numeric validation
# --------------------------------------------------------------------- #


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