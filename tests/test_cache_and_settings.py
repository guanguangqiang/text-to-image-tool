import json
from pathlib import Path

from script2gif.domain.models import AppSettings
from script2gif.infrastructure.cache_store import CacheStore, content_hash
from script2gif.infrastructure.settings_store import SettingsStore


def test_content_hash_is_stable_and_sensitive() -> None:
    first = content_hash("wan", "prompt", {"size": "2K"})
    same = content_hash("wan", "prompt", {"size": "2K"})
    different = content_hash("wan", "other", {"size": "2K"})

    assert first == same
    assert first != different


def test_cache_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"fake-png")
    cache = CacheStore(tmp_path / "cache")

    stored = cache.put("a" * 64, source)

    assert stored.read_bytes() == b"fake-png"
    assert cache.get("a" * 64) == stored


def test_settings_never_persist_api_key(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    settings = AppSettings(workspace_id="ws-123")
    store.save(settings)

    raw = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))

    assert raw["workspace_id"] == "ws-123"
    assert "api_key" not in raw
    assert "secret" not in raw
