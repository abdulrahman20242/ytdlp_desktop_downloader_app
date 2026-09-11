import json

from core.config_manager import ConfigManager


def test_defaults_are_loaded_when_no_config_file(config):
    assert config.get("ui.theme") == "dark"
    assert config.get("ui.language") == "ar"
    assert config.get("download.default_quality") == "1080p"
    assert config.get("download.retries") == 10
    assert config.get("download.merge_output_format") == "mp4"


def test_removed_fake_settings_no_longer_in_defaults(config):
    # Keys that had no UI and no runtime effect were dropped from the schema.
    for key in (
        "download.embed_thumbnail",
        "download.embed_metadata",
        "download.write_subs",
        "download.sub_langs",
        "audio.embed_thumbnail",
        "audio.mp3_quality",
        "audio.default_format",
        "advanced.ffmpeg_location",
        "advanced.js_runtime",
        "advanced.node_path",
        "advanced.use_nightly_yt_dlp",
    ):
        assert config.get(key) is None


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
    config.set("download.merge_output_format", "mkv")
    reloaded = ConfigManager()
    assert reloaded.get("download.merge_output_format") == "mkv"


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


# --------------------------------------------------------------------- #
#  F-A4: malformed / truncated config must never take the app down
# --------------------------------------------------------------------- #


def test_malformed_config_uses_defaults_and_keeps_original(config, tmp_path):
    (tmp_path / "config.json").write_text("{ not valid json !!!", encoding="utf-8")
    reloaded = ConfigManager()
    assert reloaded.get("ui.theme") == "dark"
    assert reloaded.get("download.retries") == 10
    # the unusable file is preserved in place (no destructive rewrite on load)
    assert (tmp_path / "config.json").read_text(encoding="utf-8") == "{ not valid json !!!"


def test_malformed_config_produces_backup_file(config, tmp_path):
    (tmp_path / "config.json").write_text("{ broken", encoding="utf-8")
    ConfigManager()
    backup = tmp_path / "config.json.bak"
    assert backup.read_text(encoding="utf-8") == "{ broken"


def test_non_dict_config_falls_back_to_defaults(config, tmp_path):
    (tmp_path / "config.json").write_text("[1, 2, 3]", encoding="utf-8")
    reloaded = ConfigManager()
    assert reloaded.get("ui.theme") == "dark"
    assert (tmp_path / "config.json.bak").exists()


def test_empty_config_file_is_recovered(config, tmp_path):
    (tmp_path / "config.json").write_text("", encoding="utf-8")
    reloaded = ConfigManager()
    assert reloaded.get("download.default_quality") == "1080p"


def test_truncated_json_is_recovered_with_backup(config, tmp_path):
    # an interrupted atomic-write artifact: a partial JSON document
    (tmp_path / "config.json").write_text('{"ui": {"theme": "lig', encoding="utf-8")
    reloaded = ConfigManager()
    assert reloaded.get("ui.theme") == "dark"
    assert (tmp_path / "config.json.bak").exists()


def test_partial_saved_values_survive_reload_with_defaults(config, tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps({"download": {"retries": 3}}), encoding="utf-8"
    )
    reloaded = ConfigManager()
    assert reloaded.get("download.retries") == 3
    assert reloaded.get("ui.theme") == "dark"


def test_non_dict_override_of_default_section_is_kept_not_crashing(config, tmp_path):
    # _merge must tolerate a saved value that replaces a default dict section
    (tmp_path / "config.json").write_text(
        json.dumps({"download": "a string instead of a dict"}), encoding="utf-8"
    )
    reloaded = ConfigManager()
    assert reloaded.get("download") == "a string instead of a dict"
    assert reloaded.get("ui.theme") == "dark"


def test_save_after_malformed_recovery_persists_valid_config(config, tmp_path):
    (tmp_path / "config.json").write_text("{ garbage", encoding="utf-8")
    reloaded = ConfigManager()
    reloaded.set("ui.theme", "light")
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["ui"]["theme"] == "light"
    # the unusable original is still preserved as a backup
    assert (tmp_path / "config.json.bak").read_text(encoding="utf-8") == "{ garbage"


def test_save_is_atomic_and_leaves_no_tmp_behind(config, tmp_path):
    config.set("ui.theme", "light")
    assert not list(tmp_path.glob("config.json.tmp"))
    assert json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["ui"]["theme"] == "light"


def test_save_failure_is_tolerated_and_cleans_temp(config, tmp_path, monkeypatch):
    import core.config_manager as cm

    def boom_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(cm.os, "replace", boom_replace)
    config.set("ui.theme", "light")
    # value still live in memory, no exception to the caller, no tmp litter
    assert config.get("ui.theme") == "light"
    assert not list(tmp_path.glob("config.json.tmp"))