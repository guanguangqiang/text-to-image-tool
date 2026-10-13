from dataclasses import dataclass

from script2gif.application.cleanup_service import CleanupService
from script2gif.domain.models import AppSettings
from script2gif.infrastructure.app_paths import AppPaths
from script2gif.infrastructure.cache_store import CacheStore
from script2gif.infrastructure.logging_config import configure_logging
from script2gif.infrastructure.settings_store import SettingsStore


@dataclass
class BootstrapResult:
    paths: AppPaths
    settings: AppSettings
    cleaned_bytes: int


def bootstrap() -> BootstrapResult:
    paths = AppPaths.discover()
    paths.ensure()
    configure_logging(paths.log_dir)
    settings = SettingsStore(paths.config_dir).load()
    cache = CacheStore(paths.cache_dir / "generations")
    cleanup = CleanupService(cache, paths.temp_dir)
    cleaned = cleanup.run(
        settings.cache_retention_days,
        int(settings.cache_limit_gb * 1024 * 1024 * 1024),
    )
    return BootstrapResult(paths=paths, settings=settings, cleaned_bytes=cleaned)
