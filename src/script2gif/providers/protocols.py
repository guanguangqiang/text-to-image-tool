from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Protocol

from pydantic import BaseModel, Field

from script2gif.domain.models import StoryboardDraft


class ImageRequest(BaseModel):
    prompt: str
    model: str = "wan2.7-image-pro"
    size: str = "2K"
    reference_images: List[Path] = Field(default_factory=list)


class RemoteTask(BaseModel):
    id: str
    status: str
    result_url: Optional[str] = None
    error: Optional[str] = None


class StoryboardPlanner(Protocol):
    def create_storyboard(self, script: str, style: str) -> StoryboardDraft: ...


class ImageGenerator(Protocol):
    def submit(self, request: ImageRequest) -> str: ...

    def get_task(self, task_id: str) -> RemoteTask: ...

    def download(self, url: str, destination: Path) -> Path: ...
