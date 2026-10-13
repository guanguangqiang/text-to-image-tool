from pathlib import Path

import pytest
from pydantic import ValidationError

from script2gif.domain.enums import MotionType
from script2gif.domain.models import Project, Shot, StoryboardDraft


def make_shot(index: int = 1) -> Shot:
    return Shot(
        index=index,
        scene="清晨森林",
        action="小狐狸从树后探出头",
        camera="中景缓慢推进",
        image_prompt="治愈绘本风格，清晨森林中的小狐狸",
        motion=MotionType.ZOOM_IN,
    )


def test_storyboard_normalizes_shot_indices() -> None:
    draft = StoryboardDraft(shots=[make_shot(7), make_shot(9)])

    assert [shot.index for shot in draft.shots] == [1, 2]


def test_shot_rejects_excessive_duration() -> None:
    with pytest.raises(ValidationError):
        Shot.model_validate({**make_shot().model_dump(), "duration_seconds": 31})


def test_project_resolve_rejects_path_escape(tmp_path: Path) -> None:
    project = Project(name="测试")

    with pytest.raises(ValueError, match="escapes"):
        project.resolve(tmp_path, "../secret.txt")
