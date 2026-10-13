from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from script2gif.domain.enums import (
    MotionType,
    ProjectStatus,
    ShotStatus,
    TaskStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Character(BaseModel):
    id: str = Field(default_factory=lambda: f"char_{uuid4().hex[:8]}")
    name: str = Field(min_length=1, max_length=100)
    appearance: str = Field(min_length=1, max_length=2000)
    clothing: Optional[str] = Field(default=None, max_length=1000)
    reference_images: List[str] = Field(default_factory=list)


class Shot(BaseModel):
    id: str = Field(default_factory=lambda: f"shot_{uuid4().hex[:8]}")
    index: int = Field(ge=1)
    duration_seconds: float = Field(default=4.0, ge=1.0, le=30.0)
    scene: str = Field(min_length=1, max_length=3000)
    action: str = Field(min_length=1, max_length=3000)
    camera: str = Field(default="缓慢推进", max_length=500)
    characters: List[str] = Field(default_factory=list)
    image_prompt: str = Field(min_length=1, max_length=5000)
    subtitle: Optional[str] = Field(default=None, max_length=500)
    motion: MotionType = MotionType.ZOOM_IN
    status: ShotStatus = ShotStatus.PENDING
    keyframe_path: Optional[str] = None
    video_path: Optional[str] = None
    error: Optional[str] = None


class TaskRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"job_{uuid4().hex[:10]}")
    shot_id: Optional[str] = None
    task_type: str
    provider: str
    remote_task_id: Optional[str] = None
    request_hash: str
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = Field(default=0, ge=0)
    output_path: Optional[str] = None
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProjectSettings(BaseModel):
    aspect_ratio: str = "16:9"
    image_size: str = "2048*1152"
    planner_model: str = "qwen3.8-flash"
    image_model: str = "wan2.7-image-pro"
    motion_mode: str = "local"
    output_width: int = Field(default=1280, ge=320, le=3840)
    output_height: int = Field(default=720, ge=240, le=2160)
    video_fps: int = Field(default=24, ge=10, le=60)
    gif_fps: int = Field(default=12, ge=5, le=30)

    @field_validator("aspect_ratio")
    @classmethod
    def validate_aspect_ratio(cls, value: str) -> str:
        if value not in {"16:9", "9:16", "1:1", "4:3", "3:4"}:
            raise ValueError("unsupported aspect ratio")
        return value


class StoryboardDraft(BaseModel):
    title: str = Field(default="未命名项目", max_length=200)
    style: str = Field(default="电影感插画", max_length=1000)
    characters: List[Character] = Field(default_factory=list)
    shots: List[Shot] = Field(min_length=1, max_length=30)

    @field_validator("shots")
    @classmethod
    def normalize_shot_indices(cls, shots: List[Shot]) -> List[Shot]:
        for index, shot in enumerate(shots, start=1):
            shot.index = index
        return shots


class Project(BaseModel):
    schema_version: int = 1
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str = Field(min_length=1, max_length=200)
    style: str = "电影感插画"
    script_path: str = "script.txt"
    characters: List[Character] = Field(default_factory=list)
    shots: List[Shot] = Field(default_factory=list)
    tasks: List[TaskRecord] = Field(default_factory=list)
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    status: ProjectStatus = ProjectStatus.DRAFT
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def resolve(self, project_dir: Path, relative_path: Optional[str]) -> Optional[Path]:
        if not relative_path:
            return None
        candidate = (project_dir / relative_path).resolve()
        project_root = project_dir.resolve()
        if candidate != project_root and project_root not in candidate.parents:
            raise ValueError("project path escapes the project directory")
        return candidate


class AppSettings(BaseModel):
    workspace_id: str = ""
    region: str = "cn-beijing"
    qwen_model: str = "qwen3.8-flash"
    image_model: str = "wan2.7-image-pro"
    ffmpeg_path: str = ""
    image_concurrency: int = Field(default=2, ge=1, le=5)
    cache_limit_gb: float = Field(default=5.0, ge=0.5, le=100.0)
    cache_retention_days: int = Field(default=30, ge=1, le=365)
    extra: Dict[str, Any] = Field(default_factory=dict)

    @property
    def api_base_url(self) -> str:
        if not self.workspace_id:
            return ""
        suffix = "maas.aliyuncs.com"
        return f"https://{self.workspace_id}.{self.region}.{suffix}"

    @property
    def compatible_base_url(self) -> str:
        base = self.api_base_url
        return f"{base}/compatible-mode/v1" if base else ""
