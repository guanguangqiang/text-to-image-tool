from pathlib import Path

from script2gif.application.storyboard_service import StoryboardService
from script2gif.domain.enums import ProjectStatus
from script2gif.domain.models import Project, Shot, StoryboardDraft
from script2gif.infrastructure.project_store import LocalProjectStore


class FakePlanner:
    def create_storyboard(self, script: str, style: str) -> StoryboardDraft:
        assert script == "测试剧本"
        assert style == "水彩"
        return StoryboardDraft(
            title="生成标题",
            style=style,
            shots=[
                Shot(
                    index=1,
                    scene="森林",
                    action="狐狸奔跑",
                    camera="远景",
                    image_prompt="水彩森林中的狐狸",
                )
            ],
        )


def test_generate_storyboard_persists_result(tmp_path: Path) -> None:
    store = LocalProjectStore()
    project = Project(name="原项目", style="水彩")
    store.initialize(tmp_path, project)

    result = StoryboardService(store).generate(tmp_path, project, "测试剧本", FakePlanner())

    assert result.name == "生成标题"
    assert result.status == ProjectStatus.WAITING_APPROVAL
    assert len(store.load(tmp_path).shots) == 1
    assert store.read_script(tmp_path, result) == "测试剧本"
