import json
from pathlib import Path

import pytest

import core.config_manager as cm
from core.config_manager import ConfigManager


def _redirect_to(tmp_path, monkeypatch, name="config.json"):
    cfg_path = tmp_path / name
    monkeypatch.setattr(cm, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(cm, "config_path", lambda: cfg_path)
    return cfg_path


def _legacy_install(monkeypatch, tmp_path, config_text, cookies_text=None):
    app_root = tmp_path / "approot"
    data_dir = app_root / "data"
    data_dir.mkdir(parents=True)
    legacy_config = data_dir / "config.json"
    legacy_config.write_text(config_text, encoding="utf-8")
    if cookies_text is not None:
        (data_dir / "cookies.txt").write_text(cookies_text, encoding="utf-8")
    cookies_path = tmp_path / "cookies.txt"
    monkeypatch.setattr(cm, "app_root", lambda: app_root)
    monkeypatch.setattr(cm, "cookies_path", lambda: cookies_path)
    return legacy_config, cookies_path


# --------------------------------------------------------------------- #
#  Legacy app-folder migration
# --------------------------------------------------------------------- #


def test_legacy_migration_ports_config_and_cookies(tmp_path, monkeypatch):
    dev_dir = "F:/projects/yt-dlp/ytdlp_desktop_downloader_app/downloads"
    cfg_path = _redirect_to(tmp_path, monkeypatch)
    _, cookies_path = _legacy_install(
        monkeypatch,
        tmp_path,
        json.dumps({"ui": {"theme": "light"}, "download": {"default_dir": dev_dir, "retries": 5}}),
        cookies_text="NID=abc",
    )

    migrated = ConfigManager()
    assert migrated.get("ui.theme") == "light"
    assert migrated.get("download.retries") == 5
    assert "ytdlp_desktop_downloader_app" not in migrated.get("download.default_dir")
    assert cookies_path.read_text(encoding="utf-8") == "NID=abc"
    assert cfg_path.exists()


def test_legacy_migration_with_no_legacy_files_leaves_no_config(tmp_path, monkeypatch):
    cfg_path = _redirect_to(tmp_path, monkeypatch)
    app_root = tmp_path / "approot"
    (app_root / "data").mkdir(parents=True)
    monkeypatch.setattr(cm, "app_root", lambda: app_root)
    monkeypatch.setattr(cm, "cookies_path", lambda: tmp_path / "cookies.txt")

    ConfigManager()
    assert not cfg_path.exists()
    assert not (tmp_path / "cookies.txt").exists()


def test_legacy_migration_skips_when_config_already_exists(tmp_path, monkeypatch):
    cfg_path = _redirect_to(tmp_path, monkeypatch)
    cfg_path.write_text(json.dumps({"download": {"retries": 9}}), encoding="utf-8")
    legacy_config, cookies_path = _legacy_install(
        monkeypatch, tmp_path,
        json.dumps({"ui": {"theme": "light"}}),
        cookies_text="SESSION=old",
    )

    reloaded = ConfigManager()
    # existing user config and cookies take precedence over the legacy copy
    assert reloaded.get("download.retries") == 9
    assert reloaded.get("ui.theme") != "light"
    # legacy cookies are still ported because no user cookies file exists yet
    assert cookies_path.read_text(encoding="utf-8") == "SESSION=old"
    assert legacy_config.parent == tmp_path / "approot" / "data"


def test_legacy_migration_logs_warning_when_dir_creation_fails(tmp_path, monkeypatch, caplog):
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file", encoding="utf-8")
    cfg_path = blocker / "config.json"
    monkeypatch.setattr(cm, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(cm, "config_path", lambda: cfg_path)

    with caplog.at_level("WARNING", logger="core.config_manager"):
        conf = ConfigManager()
    assert "Could not create user data directory" in caplog.text
    assert conf.get("ui.theme") == "dark"


# --------------------------------------------------------------------- #
#  Legacy config file porting
# --------------------------------------------------------------------- #


def test_unparseable_legacy_config_is_copied_verbatim(tmp_path, monkeypatch):
    cfg_path = _redirect_to(tmp_path, monkeypatch)
    legacy = tmp_path / "legacy.json"
    legacy.write_text("{ malformed", encoding="utf-8")

    manager = object.__new__(ConfigManager)
    manager._copy_legacy_config(legacy)
    assert cfg_path.read_text(encoding="utf-8") == "{ malformed"


def test_unparseable_legacy_config_copy_failure_is_logged(tmp_path, monkeypatch, caplog):
    _redirect_to(tmp_path, monkeypatch)
    legacy = tmp_path / "legacy.json"
    legacy.write_text("{ malformed", encoding="utf-8")

    def boom(src, dst):
        raise OSError("no permission")

    monkeypatch.setattr(cm.shutil, "copy2", boom)
    manager = object.__new__(ConfigManager)
    with caplog.at_level("WARNING", logger="core.config_manager"):
        manager._copy_legacy_config(legacy)
    assert "Could not migrate legacy config" in caplog.text


def test_parseable_legacy_config_is_sanitized_then_written(tmp_path, monkeypatch):
    cfg_path = _redirect_to(tmp_path, monkeypatch)
    repo_dir = "C:/dev/ytdlp_desktop_downloader_app/out"
    legacy = tmp_path / "legacy.json"
    legacy.write_text(
        json.dumps({"download": {"default_dir": repo_dir, "retries": 7}}),
        encoding="utf-8",
    )

    manager = object.__new__(ConfigManager)
    manager._copy_legacy_config(legacy)
    written = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert "ytdlp_desktop_downloader_app" not in written["download"]["default_dir"]
    assert written["download"]["retries"] == 7


def test_legacy_config_write_failure_is_logged(tmp_path, monkeypatch, caplog):
    cfg_path = _redirect_to(tmp_path, monkeypatch)
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({"ui": {"theme": "light"}}), encoding="utf-8")

    real_open = open

    def read_only_open(file, mode="r", **kwargs):
        if str(file) == str(cfg_path) and "w" in mode:
            raise OSError("readonly fs")
        return real_open(file, mode, **kwargs)

    monkeypatch.setattr(cm, "open", read_only_open, raising=False)
    manager = object.__new__(ConfigManager)
    with caplog.at_level("WARNING", logger="core.config_manager"):
        manager._copy_legacy_config(legacy)
    assert "Could not migrate legacy config" in caplog.text


# --------------------------------------------------------------------- #
#  Sanitisation edge cases
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw_input",
    [
        [1, 2, 3],
        "a string",
        {"ui": {"theme": "light"}, "custom_key": "kept"},
        {"download": "scalar"},
    ],
)
def test_sanitize_legacy_settings_preserves_non_conforming_or_unaffected_inputs(raw_input):
    manager = ConfigManager()
    assert manager._sanitize_legacy_settings(raw_input) == raw_input


# --------------------------------------------------------------------- #
#  Repository-path detection
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("value", [None, "", "   ", 42])
def test_is_repository_path_blank_values_are_not_repo(value):
    assert ConfigManager._is_repository_path(value) is False


def test_is_repository_path_abs_dev_root_is_repo(monkeypatch):
    # defined after the substring pass; validated relative to app_root()
    dev_root = Path.cwd()
    out = dev_root / "downloads"
    monkeypatch.setattr(cm, "app_root", lambda: dev_root)
    assert ConfigManager._is_repository_path(str(out)) is True


def test_is_repository_path_returns_false_when_resolve_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("unresolvable")

    monkeypatch.setattr(cm.Path, "resolve", boom)
    assert ConfigManager._is_repository_path("C:\\any\\absolute\\path") is False


# --------------------------------------------------------------------- #
#  Merge / get / save error branches
# --------------------------------------------------------------------- #


def test_merge_returns_deepcopy_for_non_dict_override():
    manager = ConfigManager()
    base = manager._defaults
    merged = manager._merge(base, [1, 2, 3])
    assert merged == base
    assert merged is not base


def test_get_returns_default_when_path_crosses_scalar_node(config):
    config._data = {"ui": 5}
    assert config.get("ui.theme", "fallback") == "fallback"


def test_save_cleanup_failure_is_logged_as_warning(config, tmp_path, monkeypatch, caplog):
    def boom_replace(src, dst):
        raise OSError("disk full")

    def boom_unlink(self, missing_ok=True):
        raise OSError("file busy")

    monkeypatch.setattr(cm.os, "replace", boom_replace)
    monkeypatch.setattr(cm.Path, "unlink", boom_unlink)
    with caplog.at_level("WARNING", logger="core.config_manager"):
        assert config.set("ui.theme", "light") is False
    assert "Could not remove failed config temp file" in caplog.text


# --------------------------------------------------------------------- #
#  Bad-config recovery when backup fails
# --------------------------------------------------------------------- #


def test_backup_bad_config_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "CONFIG_PATH", tmp_path / "absent.json")
    manager = object.__new__(ConfigManager)
    assert manager._backup_bad_config() is None


def test_recover_warns_without_backup_when_copy_fails(tmp_path, monkeypatch, caplog):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{ garbage", encoding="utf-8")
    monkeypatch.setattr(cm, "CONFIG_PATH", cfg_path)

    def boom(src, dst):
        raise OSError("locked")

    monkeypatch.setattr(cm.shutil, "copy2", boom)
    with caplog.at_level("WARNING", logger="core.config_manager"):
        ConfigManager()
    assert "Could not back up unusable config" in caplog.text
    assert "using defaults." in caplog.text