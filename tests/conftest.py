import json, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def config():
    cfg = json.loads((ROOT / "config" / "scoring.json").read_text(encoding="utf-8"))
    cfg["favourites"]["teams"] = []
    return cfg
