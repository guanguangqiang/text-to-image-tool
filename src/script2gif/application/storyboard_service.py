from pathlib import Path

from script2gif.domain.enums import ProjectStatus, ShotStatus
from script2gif.domain.models import Project
from script2gif.infrastructure.project_store import LocalProjectStore
from script2gif.providers.protocols import StoryboardPlanner


class StoryboardService:
    def __init__(self, store: LocalProjectStore) -> None:
        self.store = store

    def generate(
        self,
        project_dir: Path,
        project: Project,
        script: str,
        planner: StoryboardPlanner,
    ) -> Project:
        project.status = ProjectStatus.PLANNING
        self.store.write_script(project_dir, script)
        self.store.save(project_dir, project)
        try:
            draft = planner.create_storyboard(script, project.style)
            project.name = draft.title or project.name
            project.style = draft.style or project.style
            project.characters = draft.characters
            project.shots = draft.shots
            for shot in project.shots:
                shot.status = ShotStatus.PENDING
                shot.error = None
            project.status = ProjectStatus.WAITING_APPROVAL
            self.store.save(project_dir, project)
            return project
        except Exception:
            project.status = ProjectStatus.FAILED
            self.store.save(project_dir, project)
            raise
