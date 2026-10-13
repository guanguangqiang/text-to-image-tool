from pathlib import Path

from script2gif.application.generation_service import ImageGenerationService
from script2gif.domain.enums import ShotStatus, TaskStatus
from script2gif.domain.models import Project, Shot
from script2gif.infrastructure.cache_store import CacheStore
from script2gif.infrastructure.project_store import LocalProjectStore
from script2gif.providers.protocols import ImageRequest, RemoteTask


class FakeImageProvider:
    def __init__(self) -> None:
        self.submissions = 0

    def submit(self, request: ImageRequest) -> str:
        self.submissions += 1
        assert request.model == "wan2.7-image-pro"
        return "remote-123"

    def get_task(self, task_id: str) -> RemoteTask:
        return RemoteTask(id=task_id, status="SUCCEEDED", result_url="https://example/image")

    def download(self, url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"generated-image")
        return destination


def test_image_generation_persists_remote_task_and_uses_cache(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    store = LocalProjectStore()
    project = Project(
        name="测试",
        shots=[
            Shot(
                index=1,
                scene="森林",
                action="狐狸奔跑",
                camera="中景",
                image_prompt="森林中的狐狸",
            )
        ],
    )
    store.initialize(project_dir, project)
    provider = FakeImageProvider()
    service = ImageGenerationService(store, CacheStore(tmp_path / "cache"))

    output = service.generate_shot(project_dir, project, project.shots[0].id, provider)

    assert output.read_bytes() == b"generated-image"
    assert project.shots[0].status == ShotStatus.SUCCEEDED
    assert project.tasks[0].remote_task_id == "remote-123"
    assert project.tasks[0].status == TaskStatus.SUCCEEDED

    output.unlink()
    project.shots[0].status = ShotStatus.PENDING
    cached_output = service.generate_shot(project_dir, project, project.shots[0].id, provider)

    assert cached_output.read_bytes() == b"generated-image"
    assert provider.submissions == 1
