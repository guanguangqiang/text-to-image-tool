from pathlib import Path

from script2gif.domain.models import AppSettings
from script2gif.infrastructure.json_io import atomic_write_json, read_json


class SettingsStore:
    def __init__(self, config_dir: Path) -> None:
        self.path = config_dir / "settings.json"

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        return AppSettings.model_validate(read_json(self.path))

    def save(self, settings: AppSettings) -> None:
        payload = settings.model_dump(mode="json")
        for suspicious_key in ("api_key", "token", "secret", "password"):
            payload.pop(suspicious_key, None)
        atomic_write_json(self.path, payload)
