import json
import logging
import os
import shutil
from pathlib import Path

from utils.paths import app_root, config_path, cookies_path

CONFIG_PATH = config_path()

LOGGER = logging.getLogger(__name__)
_BACKUP_SUFFIX = ".bak"
_TMP_SUFFIX = ".tmp"

_DEFAULTS = {
    "version": "1.0",
    "ui": {
        "theme": "dark",
        "language": "ar",
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
            return self._defaults.copy()
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError) as e:
            self._recover_bad_config(f"could not read/parse the file: {e}")
            return self._defaults.copy()
        if not isinstance(saved, dict):
            self._recover_bad_config("root value is not a JSON object")
            return self._defaults.copy()
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
        target_dir.mkdir(parents=True, exist_ok=True)
        legacy_dir = app_root() / "data"
        if not CONFIG_PATH.exists():
            legacy_config = legacy_dir / "config.json"
            if legacy_config.exists():
                shutil.copy2(legacy_config, CONFIG_PATH)
        if not cookies_path().exists():
            legacy_cookies = legacy_dir / "cookies.txt"
            if legacy_cookies.exists():
                shutil.copy2(legacy_cookies, cookies_path())

    @property
    def _defaults(self) -> dict:
        import copy
        return copy.deepcopy(_DEFAULTS)

    def _merge(self, base: dict, override: dict) -> dict:
        if not isinstance(override, dict):
            return base.copy()
        result = base.copy()
        for k, v in override.items():
            if isinstance(v, dict) and k in result and isinstance(result[k], dict):
                result[k] = self._merge(result[k], v)
            else:
                result[k] = v
        return result

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

    def set(self, key_path: str, value):
        keys = key_path.split(".")
        obj = self._data
        for k in keys[:-1]:
            obj = obj.setdefault(k, {})
        obj[keys[-1]] = value
        self._save()

    def _save(self):
        """Persist atomically: write to a temp file next to the target, then
        ``os.replace`` so an interrupted write can never leave a truncated
        ``config.json`` behind (which previously made the app fail to boot).
        """
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_name(CONFIG_PATH.name + _TMP_SUFFIX)
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.flush()
            os.replace(tmp, CONFIG_PATH)
        except OSError as e:
            LOGGER.error("Could not save config to %s: %s", CONFIG_PATH, e)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def reset_to_defaults(self):
        self._data = self._defaults
        self._save()
