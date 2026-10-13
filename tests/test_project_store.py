import json
from pathlib import Path

from script2gif.application.project_service import ProjectService
from script2gif.domain.models import Project
from script2gif.infrastructure.project_store import LocalProjectStore


def test_project_round_trip(tmp_path: Path) -> None:
    store = LocalProjectStore()
    project = Project(name="森林故事")
    project_dir = tmp_path / "forest"

    store.initialize(project_dir, project, "从前有一只狐狸。")
    loaded = store.load(project_dir)

    assert loaded.id == project.id
    assert store.read_script(project_dir, loaded) == "从前有一只狐狸。"
    assert (project_dir / "assets" / "keyframes").is_dir()
    assert not (project_dir / ".project.json.tmp").exists()


def test_project_service_sanitizes_windows_directory_name(tmp_path: Path) -> None:
    service = ProjectService(LocalProjectStore())

    project_dir, project = service.create(tmp_path, "狐狸:故事")

    assert project.name == "狐狸:故事"
    assert project_dir.name == "狐狸_故事"


def test_saved_paths_stay_relative(tmp_path: Path) -> None:
    store = LocalProjectStore()
    project = Project(name="portable")
    project_dir = tmp_path / "portable"
    store.initialize(project_dir, project)

    payload = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))

    assert payload["script_path"] == "script.txt"
    assert str(tmp_path) not in json.dumps(payload)
