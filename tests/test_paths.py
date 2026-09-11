from pathlib import Path
from types import SimpleNamespace

from utils import paths


def test_is_frozen_false_in_tests():
    assert paths.is_frozen() is False


def test_app_root_points_at_project_root():
    assert paths.app_root().resolve() == Path(__file__).resolve().parent.parent


def _freeze(paths_mod, exe_dir):
    paths_mod.sys = SimpleNamespace(frozen=True, executable=str(exe_dir / "YTDownloaderCore.exe"))


def test_app_root_uses_executable_dir_when_frozen(monkeypatch, tmp_path):
    _freeze(paths, tmp_path)
    assert paths.app_root() == tmp_path
    assert paths.is_frozen() is True


def test_bin_dir_tracks_app_root(monkeypatch, tmp_path):
    _freeze(paths, tmp_path)
    assert paths.bin_dir() == tmp_path / "bin"


def test_assets_dir_tracks_app_root(monkeypatch, tmp_path):
    _freeze(paths, tmp_path)
    assert paths.assets_dir() == tmp_path / "assets"


def test_user_data_dir_uses_appdata_when_present(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    d = paths.user_data_dir()
    assert d == tmp_path / "roaming" / "YTDownloader"
    assert d.is_dir()


def test_user_data_dir_uses_home_dir_when_appdata_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    d = paths.user_data_dir()
    assert d == tmp_path / "YTDownloader"
    assert d.is_dir()


def test_user_data_dir_falls_back_to_dotfolder_when_brand_dir_blocked(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "YTDownloader").write_text("not a directory", encoding="utf-8")
    d = paths.user_data_dir()
    assert d == tmp_path / ".ytdownloader"
    assert d.is_dir()


def test_config_and_cookies_live_inside_user_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    assert paths.config_path() == tmp_path / "roaming" / "YTDownloader" / "config.json"
    assert paths.cookies_path() == tmp_path / "roaming" / "YTDownloader" / "cookies.txt"