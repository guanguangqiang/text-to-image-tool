from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Callable, Optional

from script2gif.domain.enums import ProjectStatus, ShotStatus, TaskStatus
from script2gif.domain.errors import ProviderError, RemoteTaskPendingError
from script2gif.domain.models import Project, TaskRecord, utc_now
from script2gif.infrastructure.cache_store import CacheStore, content_hash
from script2gif.infrastructure.project_store import LocalProjectStore
from script2gif.providers.protocols import ImageGenerator, ImageRequest

ProgressCallback = Callable[[int, int, str], None]


class ImageGenerationService:
    TERMINAL_FAILURES = {"FAILED", "CANCELED", "CANCELLED", "UNKNOWN"}

    def __init__(self, store: LocalProjectStore, cache: CacheStore) -> None:
        self.store = store
        self.cache = cache

    def generate_all(
        self,
        project_dir: Path,
        project: Project,
        provider: ImageGenerator,
        progress: Optional[ProgressCallback] = None,
        poll_interval: float = 3.0,
    ) -> Project:
        pending = [shot for shot in project.shots if shot.status != ShotStatus.SUCCEEDED]
        if not pending:
            return project
        project.status = ProjectStatus.GENERATING_IMAGES
        self.store.save(project_dir, project)
        failures = 0
        for current, shot in enumerate(pending, start=1):
            if progress:
                progress(current, len(pending), f"正在生成分镜 {shot.index}")
            try:
                self.generate_shot(project_dir, project, shot.id, provider, poll_interval)
            except Exception as exc:
                failures += 1
                shot.status = ShotStatus.FAILED
                shot.error = str(exc)
                self.store.save(project_dir, project)
        project.status = (
            ProjectStatus.PARTIAL_FAILED if failures else ProjectStatus.WAITING_APPROVAL
        )
        self.store.save(project_dir, project)
        return project

    def generate_shot(
        self,
        project_dir: Path,
        project: Project,
        shot_id: str,
        provider: ImageGenerator,
        poll_interval: float = 3.0,
    ) -> Path:
        shot = next((item for item in project.shots if item.id == shot_id), None)
        if shot is None:
            raise ValueError(f"没有找到分镜：{shot_id}")
        references = self._reference_images(project_dir, project, shot.characters)
        request = ImageRequest(
            prompt=self._prompt(project, shot.image_prompt),
            model=project.settings.image_model,
            size=project.settings.image_size,
            reference_images=references,
        )
        cache_key = content_hash(
            request.model,
            request.prompt,
            request.size,
            [self._file_hash_input(path) for path in references],
        )
        output_path = project_dir / "assets" / "keyframes" / f"{shot.id}.png"
        cached = self.cache.get(cache_key)
        if cached:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cached, output_path)
            shot.keyframe_path = output_path.relative_to(project_dir).as_posix()
            shot.status = ShotStatus.SUCCEEDED
            shot.error = None
            self.store.save(project_dir, project)
            return output_path

        shot.status = ShotStatus.GENERATING
        shot.error = None
        task = TaskRecord(
            shot_id=shot.id,
            task_type="image_generation",
            provider="aliyun_wan",
            request_hash=cache_key,
            status=TaskStatus.PENDING,
            attempts=1,
        )
        project.tasks.append(task)
        self.store.save(project_dir, project)
        try:
            task.remote_task_id = provider.submit(request)
            task.status = TaskStatus.RUNNING
            task.updated_at = utc_now()
            self.store.save(project_dir, project)
            remote = provider.get_task(task.remote_task_id)
            deadline = time.monotonic() + 20 * 60
            while remote.status in {"PENDING", "RUNNING", "QUEUED"}:
                if time.monotonic() >= deadline:
                    raise RemoteTaskPendingError("图片生成等待超时，远程任务 ID 已保存，可稍后恢复")
                time.sleep(max(0.1, poll_interval))
                remote = provider.get_task(task.remote_task_id)
            if remote.status != "SUCCEEDED" or not remote.result_url:
                reason = remote.error or f"远程任务状态为 {remote.status}"
                raise ProviderError(reason)
            provider.download(remote.result_url, output_path)
            self.cache.put(cache_key, output_path)
            shot.keyframe_path = output_path.relative_to(project_dir).as_posix()
            shot.status = ShotStatus.SUCCEEDED
            task.status = TaskStatus.SUCCEEDED
            task.output_path = shot.keyframe_path
            task.updated_at = utc_now()
            self.store.save(project_dir, project)
            return output_path
        except RemoteTaskPendingError as exc:
            shot.status = ShotStatus.GENERATING
            shot.error = str(exc)
            task.status = TaskStatus.RUNNING
            task.last_error = str(exc)
            task.updated_at = utc_now()
            self.store.save(project_dir, project)
            raise
        except Exception as exc:
            shot.status = ShotStatus.FAILED
            shot.error = str(exc)
            task.status = TaskStatus.FAILED
            task.last_error = str(exc)
            task.updated_at = utc_now()
            self.store.save(project_dir, project)
            raise

    def resume_pending(
        self,
        project_dir: Path,
        project: Project,
        provider: ImageGenerator,
        poll_interval: float = 3.0,
    ) -> int:
        resumed = 0
        for task in project.tasks:
            if task.status != TaskStatus.RUNNING or not task.remote_task_id or not task.shot_id:
                continue
            remote = provider.get_task(task.remote_task_id)
            deadline = time.monotonic() + 20 * 60
            while remote.status in {"PENDING", "RUNNING", "QUEUED"}:
                if time.monotonic() >= deadline:
                    break
                time.sleep(max(0.1, poll_interval))
                remote = provider.get_task(task.remote_task_id)
            if remote.status == "SUCCEEDED" and remote.result_url:
                shot = next((item for item in project.shots if item.id == task.shot_id), None)
                if shot is None:
                    continue
                output_path = project_dir / "assets" / "keyframes" / f"{shot.id}.png"
                provider.download(remote.result_url, output_path)
                shot.keyframe_path = output_path.relative_to(project_dir).as_posix()
                shot.status = ShotStatus.SUCCEEDED
                task.status = TaskStatus.SUCCEEDED
                task.output_path = shot.keyframe_path
                self.cache.put(task.request_hash, output_path)
                resumed += 1
            elif remote.status in self.TERMINAL_FAILURES:
                task.status = TaskStatus.FAILED
                task.last_error = remote.error or f"远程任务状态为 {remote.status}"
                shot = next((item for item in project.shots if item.id == task.shot_id), None)
                if shot:
                    shot.status = ShotStatus.FAILED
                    shot.error = task.last_error
        self.store.save(project_dir, project)
        return resumed

    def _reference_images(
        self,
        project_dir: Path,
        project: Project,
        character_ids: list[str],
    ) -> list[Path]:
        images: list[Path] = []
        wanted = set(character_ids)
        for character in project.characters:
            if character.id not in wanted:
                continue
            for relative in character.reference_images:
                resolved = project.resolve(project_dir, relative)
                if resolved and resolved.exists():
                    images.append(resolved)
        return images[:9]

    @staticmethod
    def _prompt(project: Project, shot_prompt: str) -> str:
        return (
            f"整体风格：{project.style}。\n"
            f"画面要求：{shot_prompt}\n"
            "连续性要求：保持角色脸型、发型、服装和配色一致。\n"
            "限制要求：画面中不要出现文字、水印、边框和多余角色。"
        )

    @staticmethod
    def _file_hash_input(path: Path) -> tuple[str, int, int]:
        stat = path.stat()
        return path.name, stat.st_size, stat.st_mtime_ns
