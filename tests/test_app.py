import os

import pytest

import app as app_module
from app import main


class _FakeConfig:
    def __init__(self, data):
        self._data = data

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


class _FakeRoot:
    def __init__(self):
        self.calls = []
        self.title_text = None
        self.geometry_str = None
        self.minsize_args = None
        self.mainloops = 0

    def title(self, text):
        self.title_text = text

    def geometry(self, value):
        self.geometry_str = value

    def minsize(self, w, h):
        self.minsize_args = (w, h)

    def grid_columnconfigure(self, *args, **kwargs):
        self.calls.append(("grid_columnconfigure", args, kwargs))

    def grid_rowconfigure(self, *args, **kwargs):
        self.calls.append(("grid_rowconfigure", args, kwargs))

    def iconbitmap(self, path):
        self.calls.append(("iconbitmap", path))

    def mainloop(self):
        self.mainloops += 1


def _patch_bootstrap(monkeypatch, config=None):
    monkeypatch.setattr(app_module, "ConfigManager", lambda: config or _FakeConfig({}))
    monkeypatch.setattr(app_module.ctk, "set_appearance_mode", lambda mode: None)
    root = _FakeRoot()
    monkeypatch.setattr(app_module.ctk, "CTk", lambda: root)
    created = {"main_window": [], "startup": []}

    class FakeStartupCheckFrame:
        def __init__(self, master, on_done):
            created["startup"].append((master, on_done))

    monkeypatch.setattr(app_module, "StartupCheckFrame", FakeStartupCheckFrame)
    monkeypatch.setattr(app_module, "MainWindow", lambda master, config: created["main_window"].append((master, config)))
    return root, created


@pytest.mark.parametrize("flag", ["1", "0", "true", "yes"])
def test_main_selftest_returns_before_gui(monkeypatch, flag):
    monkeypatch.setenv("YTDLP_DESKTOP_SELFTEST", flag)
    monkeypatch.setattr(app_module, "ConfigManager", lambda: _FakeConfig({}))
    monkeypatch.setattr(app_module.ctk, "set_appearance_mode", lambda mode: pytest.fail("GUI side effect"))
    monkeypatch.setattr(app_module.ctk, "CTk", lambda: pytest.fail("window created"))
    main()


def test_main_bootstraps_full_gui(monkeypatch):
    root, created = _patch_bootstrap(
        monkeypatch,
        _FakeConfig({"ui": {"theme": "light", "window_width": 900, "window_height": 700}}),
    )
    main()
    assert root.title_text == "YT Downloader v1.0.0"
    assert root.geometry_str == "900x700"
    assert root.minsize_args == (700, 500)
    assert created["startup"] and created["startup"][0][0] is root
    on_done = created["startup"][0][1]
    assert created["main_window"] == []
    on_done()
    assert len(created["main_window"]) == 1
    assert created["main_window"][0][0] is root
    assert root.mainloops == 1


def test_main_applies_icon_when_present(monkeypatch, tmp_path):
    ico = tmp_path / "app.ico"
    ico.write_bytes(b"icon")
    monkeypatch.setattr(app_module, "assets_dir", lambda: tmp_path)
    root, _ = _patch_bootstrap(monkeypatch)
    main()
    assert ("iconbitmap", str(ico)) in root.calls


def test_main_skips_icon_when_assets_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "assets_dir", lambda: tmp_path)
    root, _ = _patch_bootstrap(monkeypatch)
    main()
    assert not [c for c in root.calls if c[0] == "iconbitmap"]


def test_main_logs_icon_error(monkeypatch, caplog):
    def boom():
        raise OSError("no icons here")

    monkeypatch.setattr(app_module, "assets_dir", boom)
    root, _ = _patch_bootstrap(monkeypatch)
    with caplog.at_level("DEBUG", logger="app"):
        main()
    assert "Could not set window icon" in caplog.text
    assert not [c for c in root.calls if c[0] == "iconbitmap"]


def test_main_uses_default_theme_and_size(monkeypatch):
    root, _ = _patch_bootstrap(monkeypatch, _FakeConfig({}))
    main()
    assert root.geometry_str == "800x600"
    assert root.minsize_args == (700, 500)