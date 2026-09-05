import json
from pathlib import Path

CONFIG_PATH = Path("data/config.json")

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
        "file_path": "data/cookies.txt",
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
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            return self._merge(self._defaults, saved)
        return self._defaults.copy()

    @property
    def _defaults(self) -> dict:
        import copy
        return copy.deepcopy(_DEFAULTS)

    def _merge(self, base: dict, override: dict) -> dict:
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
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def reset_to_defaults(self):
        self._data = self._defaults
        self._save()
