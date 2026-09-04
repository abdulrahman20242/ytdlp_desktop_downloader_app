import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def config(tmp_path, monkeypatch):
    import core.config_manager as cm

    monkeypatch.setattr(cm, "CONFIG_PATH", tmp_path / "config.json")
    return cm.ConfigManager()