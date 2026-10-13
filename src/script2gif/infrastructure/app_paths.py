from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_path, user_config_path, user_log_path


@dataclass(frozen=True)
class AppPaths:
    config_dir: Path
    cache_dir: Path
    log_dir: Path
    temp_dir: Path

    @classmethod
    def discover(cls) -> "AppPaths":
        app_name = "Script2Gif"
        cache_dir = Path(user_cache_path(app_name, appauthor=False))
        return cls(
            config_dir=Path(user_config_path(app_name, appauthor=False)),
            cache_dir=cache_dir,
            log_dir=Path(user_log_path(app_name, appauthor=False)),
            temp_dir=cache_dir / "temp",
        )

    def ensure(self) -> None:
        for path in (self.config_dir, self.cache_dir, self.log_dir, self.temp_dir):
            path.mkdir(parents=True, exist_ok=True)
