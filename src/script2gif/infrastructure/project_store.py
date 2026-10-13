from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import portalocker

from script2gif.domain.errors import ProjectStoreError
from script2gif.domain.models import Project
from script2gif.infrastructure.json_io import atomic_write_json, read_json


class LocalProjectStore:
    PROJECT_FILE = "project.json"
    REQUIRED_DIRECTORIES = (
        "characters",
        "shots",
        "assets/references",
        "assets/keyframes",
        "assets/videos",
        "assets/audio",
        "jobs",
        "temp",
        "outputs",
        "logs",
    )

    def initialize(self, project_dir: Path, project: Project, script: str = "") -> None:
        project_dir = project_dir.resolve()
        project_dir.mkdir(parents=True, exist_ok=True)
        for relative in self.REQUIRED_DIRECTORIES:
            (project_dir / relative).mkdir(parents=True, exist_ok=True)
        self.write_script(project_dir, script)
        self.save(project_dir, project)

    def load(self, project_dir_or_file: Path) -> Project:
        path = self._project_file(project_dir_or_file)
        if not path.exists():
            raise ProjectStoreError(f"没有找到项目文件：{path}")
        try:
            return Project.model_validate(read_json(path))
        except Exception as exc:
            raise ProjectStoreError(f"项目文件损坏或版本不兼容：{exc}") from exc

    def save(self, project_dir: Path, project: Project) -> None:
        project_dir = project_dir.resolve()
        project.updated_at = datetime.now(timezone.utc)
        path = project_dir / self.PROJECT_FILE
        try:
            with self._lock(project_dir):
                atomic_write_json(path, project.model_dump(mode="json"))
        except portalocker.LockException as exc:
            raise ProjectStoreError("项目正在被另一个程序修改，请稍后重试") from exc
        except OSError as exc:
            raise ProjectStoreError(f"无法保存项目：{exc}") from exc

    def read_script(self, project_dir: Path, project: Project) -> str:
        path = project.resolve(project_dir, project.script_path)
        if path is None or not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write_script(self, project_dir: Path, script: str) -> None:
        path = project_dir.resolve() / "script.txt"
        temporary = path.with_name(".script.txt.tmp")
        temporary.write_text(script, encoding="utf-8")
        temporary.replace(path)

    @contextmanager
    def _lock(self, project_dir: Path) -> Iterator[None]:
        lock_path = project_dir / ".project.lock"
        with portalocker.Lock(lock_path, mode="a", timeout=3):
            yield

    def _project_file(self, project_dir_or_file: Path) -> Path:
        path = project_dir_or_file.resolve()
        return path if path.name == self.PROJECT_FILE else path / self.PROJECT_FILE
