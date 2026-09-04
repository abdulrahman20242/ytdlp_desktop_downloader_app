import json

from core.config_manager import ConfigManager


def test_defaults_are_loaded_when_no_config_file(config):
    assert config.get("ui.theme") == "dark"
    assert config.get("ui.language") == "ar"
    assert config.get("download.default_quality") == "1080p"
    assert config.get("download.retries") == 10
    assert config.get("audio.mp3_quality") == "192"


def test_get_returns_default_for_missing_path(config):
    assert config.get("does.not.exist", "fallback") == "fallback"
    assert config.get("download.nope", 42) == 42


def test_get_returns_none_when_no_default_supplied(config):
    assert config.get("missing.path") is None


def test_set_creates_nested_path_and_persists(config, tmp_path):
    config.set("custom.nested.value", 123)
    assert config.get("custom.nested.value") == 123
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["custom"]["nested"]["value"] == 123


def test_set_overwrites_existing_value(config):
    config.set("ui.theme", "light")
    assert config.get("ui.theme") == "light"


def test_saved_config_is_merged_over_defaults(config, tmp_path):
    config.set("download.retries", 5)
    config.set("ui.theme", "light")

    reloaded = ConfigManager()
    assert reloaded.get("download.retries") == 5
    assert reloaded.get("ui.theme") == "light"
    assert reloaded.get("download.default_quality") == "1080p"


def test_saved_file_with_unknown_key_is_kept(config, tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps({"custom_key": "kept"}), encoding="utf-8"
    )
    reloaded = ConfigManager()
    assert reloaded.get("custom_key") == "kept"
    assert reloaded.get("ui.theme") == "dark"


def test_valid_json_saved_file_is_read(config, tmp_path):
    config.set("audio.default_format", "m4a")
    reloaded = ConfigManager()
    assert reloaded.get("audio.default_format") == "m4a"


def test_reset_to_defaults_reverts_changes(config, tmp_path):
    config.set("ui.theme", "light")
    config.set("download.retries", 99)
    config.reset_to_defaults()
    assert config.get("ui.theme") == "dark"
    assert config.get("download.retries") == 10


def test_reset_persists_defaults_to_disk(config, tmp_path):
    config.reset_to_defaults()
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["ui"]["theme"] == "dark"