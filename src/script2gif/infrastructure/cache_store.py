from __future__ import annotations

import hashlib
import json
import shutil
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def content_hash(*parts: Any) -> str:
    serialized = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class CacheStore:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, cache_key: str, suffix: str = ".png") -> Path:
        return self.cache_dir / cache_key[:2] / f"{cache_key}{suffix}"

    def get(self, cache_key: str, suffix: str = ".png") -> Path | None:
        path = self.path_for(cache_key, suffix)
        if not path.exists():
            return None
        path.touch(exist_ok=True)
        return path

    def put(self, cache_key: str, source: Path) -> Path:
        destination = self.path_for(cache_key, source.suffix.lower())
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")
        shutil.copy2(source, temporary)
        temporary.replace(destination)
        return destination

    def clean(self, retention_days: int, max_bytes: int) -> int:
        files = list(self._files())
        cutoff = time.time() - retention_days * 86400
        removed = 0
        for path in files:
            if path.stat().st_mtime < cutoff:
                removed += path.stat().st_size
                path.unlink(missing_ok=True)
        remaining = sorted(self._files(), key=lambda item: item.stat().st_mtime)
        total = sum(path.stat().st_size for path in remaining)
        for path in remaining:
            if total <= max_bytes:
                break
            size = path.stat().st_size
            path.unlink(missing_ok=True)
            total -= size
            removed += size
        return removed

    def _files(self) -> Iterable[Path]:
        return (path for path in self.cache_dir.rglob("*") if path.is_file())
