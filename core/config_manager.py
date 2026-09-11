import json
import logging
import os
import shutil
from copy import deepcopy
from pathlib import Path

from utils.paths import app_root, config_path, cookies_path

CONFIG_PATH = config_path()

LOGGER = logging.getLogger(__name__)
_BACKUP_SUFFIX = ".bak"
_TMP_SUFFIX = ".tmp"

_DEFAULTS = {
    "version": "1.0.0",
    "ui": {
        "theme": "dark",
        "window_width": 800,
        "window_height": 600,
    },
    "download": {
        "default_dir": str(Path.home() / "Downloads" / "YTDownloader"),
        "default_quality": "1080p",
        "default_mode": "video",
        "concurrent_fragments": 4,
        "retries": 10,
        "merge_output_format": "mp4",
    },
    "cookies": {
        "source": "none",
        "browser": "chrome",
        "file_path": str(cookies_path()),
    },
    "advanced": {
        "show_debug_logs": False,
        "sponsorblock_remove": False,
        "sponsorblock_categories": ["sponsor"],
    },
}


class ConfigManager:
    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        self._migrate_legacy_user_data()
        if not CONFIG_PATH.exists():
            return self._defaults
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError) as e:
            self._recover_bad_config(f"could not read/parse the file: {e}")
            return self._defaults
        if not isinstance(saved, dict):
            self._recover_bad_config("root value is not a JSON object")
            return self._defaults
        return self._merge(self._defaults, saved)

    def _recover_bad_config(self, reason: str):
        """Fall back to defaults without deleting the unusable file.

        The malformed file is kept in place and copied to ``<name>.bak`` so
        nothing is lost, the app still starts normally, and a later save
        overwrites only the broken ``config.json``.
        """
        backup = self._backup_bad_config()
        if backup:
            LOGGER.warning(
                "Config at %s is unusable (%s); backed up to %s and using defaults.",
                CONFIG_PATH, reason, backup,
            )
        else:
            LOGGER.warning("Config at %s is unusable (%s); using defaults.", CONFIG_PATH, reason)

    def _backup_bad_config(self) -> Path | None:
        if not CONFIG_PATH.exists():
            return None
        backup = CONFIG_PATH.with_name(CONFIG_PATH.name + _BACKUP_SUFFIX)
        try:
            shutil.copy2(CONFIG_PATH, backup)
            return backup
        except OSError:
            LOGGER.exception(
                "Could not back up unusable config %s to %s", CONFIG_PATH, backup
            )
            return None

    def _migrate_legacy_user_data(self):
        """Port the developer-era app-folder ``data/`` files into the per-user
        writable directory on first run.

        Only performs the move when the process is really using the default
        user-data location, so tests that redirect ``CONFIG_PATH`` to an
        isolated temp file are never disturbed.
        """
        if CONFIG_PATH != config_path():
            return
        target_dir = CONFIG_PATH.parent
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            LOGGER.warning("Could not create user data directory %s: %s", target_dir, exc)
            return
        legacy_dir = app_root() / "data"
        if not CONFIG_PATH.exists():
            legacy_config = legacy_dir / "config.json"
            if legacy_config.exists():
                self._copy_legacy_config(legacy_config)
        if not cookies_path().exists():
            legacy_cookies = legacy_dir / "cookies.txt"
            if legacy_cookies.exists():
                shutil.copy2(legacy_cookies, cookies_path())

    def _copy_legacy_config(self, legacy_config: Path):
        try:
            with open(legacy_config, encoding="utf-8") as config_file:
                legacy_settings = json.load(config_file)
        except (OSError, ValueError):
            try:
                shutil.copy2(legacy_config, CONFIG_PATH)
            except OSError as exc:
                LOGGER.warning("Could not migrate legacy config %s: %s", legacy_config, exc)
            return

        sanitized_settings = self._sanitize_legacy_settings(legacy_settings)
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as config_file:
                json.dump(sanitized_settings, config_file, ensure_ascii=False, indent=2)
        except OSError as exc:
            LOGGER.warning("Could not migrate legacy config %s: %s", legacy_config, exc)

    def _sanitize_legacy_settings(self, legacy_settings):
        if not isinstance(legacy_settings, dict):
            return legacy_settings
        sanitized_settings = deepcopy(legacy_settings)
        download_settings = sanitized_settings.get("download")
        if not isinstance(download_settings, dict):
            return sanitized_settings
        if self._is_repository_path(download_settings.get("default_dir")):
            download_settings["default_dir"] = self._defaults["download"]["default_dir"]
        return sanitized_settings

    @classmethod
    def _is_repository_path(cls, default_dir) -> bool:
        if not isinstance(default_dir, str) or not default_dir.strip():
            return False
        norm = default_dir.replace("\\", "/").lower()
        if "ytdlp_desktop_downloader_app" in norm:
            return True
        p = Path(default_dir)
        if p.is_absolute():
            try:
                return p.resolve().is_relative_to(app_root().resolve())
            except (OSError, RuntimeError, ValueError):
                return False
        return False

    @property
    def _defaults(self) -> dict:
        return deepcopy(_DEFAULTS)

    def _merge(self, base: dict, override: dict) -> dict:
        if not isinstance(override, dict):
            return deepcopy(base)
        merged_settings = deepcopy(base)
        for key, saved_value in override.items():
            default_value = merged_settings.get(key)
            if isinstance(default_value, dict):
                if isinstance(saved_value, dict):
                    merged_settings[key] = self._merge(default_value, saved_value)
                else:
                    LOGGER.warning(
                        "Config section %r has invalid non-dict type %s; restored to default structure.",
                        key,
                        type(saved_value).__name__,
                    )
                    merged_settings[key] = deepcopy(default_value)
            else:
                merged_settings[key] = saved_value
        return merged_settings
    def get(self, key_path: str, default=None):
        keys = key_path.split(".")
        obj = self._data
        for k in keys:
            if isinstance(obj, dict):
                obj = obj.get(k)
                if obj is None:
                    return default
            else:
                return default
        return obj

    def set(self, key_path: str, value) -> bool:
        keys = key_path.split(".")
        settings = self._data
        for key in keys[:-1]:
            if not isinstance(settings.get(key), dict):
                settings[key] = {}
            settings = settings[key]
        settings[keys[-1]] = value
        return self._save()
    def _save(self) -> bool:
        """Persist atomically by replacing the completed temporary file."""
        tmp = CONFIG_PATH.with_name(CONFIG_PATH.name + _TMP_SUFFIX)
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as config_file:
                json.dump(self._data, config_file, ensure_ascii=False, indent=2)
                config_file.flush()
            os.replace(tmp, CONFIG_PATH)
            return True
        except OSError as exc:
            LOGGER.error("Could not save config to %s: %s", CONFIG_PATH, exc)
            try:
                tmp.unlink(missing_ok=True)
            except OSError as cleanup_error:
                LOGGER.warning("Could not remove failed config temp file %s: %s", tmp, cleanup_error)
            return False

    def reset_to_defaults(self) -> bool:
        self._data = self._defaults
        return self._save()