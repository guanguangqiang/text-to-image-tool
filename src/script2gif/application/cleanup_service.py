import shutil
import time
from pathlib import Path

from script2gif.infrastructure.cache_store import CacheStore


class CleanupService:
    def __init__(self, cache: CacheStore, temp_dir: Path) -> None:
        self.cache = cache
        self.temp_dir = temp_dir

    def run(self, retention_days: int, max_cache_bytes: int) -> int:
        removed = self.cache.clean(retention_days, max_cache_bytes)
        cutoff = time.time() - 86400
        if self.temp_dir.exists():
            for path in self.temp_dir.iterdir():
                if path.stat().st_mtime >= cutoff:
                    continue
                if path.is_dir():
                    removed += sum(
                        item.stat().st_size for item in path.rglob("*") if item.is_file()
                    )
                    shutil.rmtree(path)
                else:
                    removed += path.stat().st_size
                    path.unlink(missing_ok=True)
        return removed
