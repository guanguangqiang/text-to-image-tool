from pathlib import Path

from script2gif.domain.models import Project
from script2gif.infrastructure.project_store import LocalProjectStore


class ProjectService:
    def __init__(self, store: LocalProjectStore) -> None:
        self.store = store

    def create(self, parent_dir: Path, name: str, script: str = "") -> tuple[Path, Project]:
        safe_name = self._safe_directory_name(name)
        project_dir = (parent_dir / safe_name).resolve()
        if (project_dir / self.store.PROJECT_FILE).exists():
            raise FileExistsError(f"项目已经存在：{project_dir}")
        project = Project(name=name.strip())
        self.store.initialize(project_dir, project, script)
        return project_dir, project

    def save(self, project_dir: Path, project: Project, script: str) -> None:
        self.store.write_script(project_dir, script)
        self.store.save(project_dir, project)

    def open(self, project_dir_or_file: Path) -> tuple[Path, Project, str]:
        project = self.store.load(project_dir_or_file)
        project_dir = (
            project_dir_or_file.parent
            if project_dir_or_file.name == self.store.PROJECT_FILE
            else project_dir_or_file
        ).resolve()
        script = self.store.read_script(project_dir, project)
        return project_dir, project, script

    @staticmethod
    def _safe_directory_name(name: str) -> str:
        value = name.strip()
        if not value:
            raise ValueError("项目名称不能为空")
        forbidden = '<>:"/\\|?*'
        safe = "".join("_" if char in forbidden else char for char in value).strip(" .")
        if not safe:
            raise ValueError("项目名称不合法")
        return safe[:100]
