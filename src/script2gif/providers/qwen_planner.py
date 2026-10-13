from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from script2gif.domain.errors import ProviderError
from script2gif.domain.models import StoryboardDraft

SYSTEM_PROMPT = """你是一名专业影视分镜师。把用户剧本拆成连续、可生成图片的分镜。
只返回一个 JSON 对象，不要返回 Markdown。JSON 必须满足以下结构：
{
  "title": "作品标题",
  "style": "统一视觉风格",
  "characters": [
    {"id":"char_001","name":"角色名","appearance":"稳定且详细的外观","clothing":"服装","reference_images":[]}
  ],
  "shots": [
    {
      "id":"shot_001","index":1,"duration_seconds":4,
      "scene":"场景环境","action":"画面动作","camera":"镜头语言",
      "characters":["char_001"],"image_prompt":"完整中文生图提示词",
      "subtitle":"字幕或旁白，没有则为 null","motion":"zoom_in"
    }
  ]
}
规则：
1. 每个镜头 2-8 秒，只描述一个主要动作；最多 30 个镜头。
2. image_prompt 必须包含主体、环境、构图、光线、镜头和统一风格。
3. 不要让图片包含文字、水印、边框；字幕由本地程序添加。
4. motion 只能是 static、zoom_in、zoom_out、pan_left、pan_right、pan_up、pan_down。
5. 人物名称必须对应 characters 中的 id，所有镜头保持人物外貌与服装一致。
"""


class QwenStoryboardPlanner:
    def __init__(self, api_key: str, base_url: str, model: str = "qwen3.8-flash") -> None:
        if not base_url:
            raise ProviderError("缺少百炼 Workspace ID，无法构造接口地址")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError("缺少 openai 依赖，请重新安装应用") from exc
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
        self._model = model

    def create_storyboard(self, script: str, style: str) -> StoryboardDraft:
        script = script.strip()
        if not script:
            raise ProviderError("剧本不能为空")
        user_prompt = f"指定视觉风格：{style}\n\n剧本：\n{script}"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        try:
            content = self._complete(messages)
            try:
                return self._validate(content)
            except ProviderError as first_error:
                repair_messages = [
                    *messages,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "上面的 JSON 无法通过数据校验。请只返回修复后的完整 JSON，"
                            f"不要解释。校验错误：{first_error}"
                        ),
                    },
                ]
                return self._validate(self._complete(repair_messages))
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"千问分镜生成失败：{exc}") from exc

    def _complete(self, messages: list[dict[str, str]]) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format={"type": "json_object"},
            extra_body={"enable_thinking": False},
        )
        content = response.choices[0].message.content
        if not content:
            raise ProviderError("千问没有返回分镜内容")
        return content

    def _validate(self, content: str) -> StoryboardDraft:
        try:
            payload: Any = json.loads(content)
            return StoryboardDraft.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise ProviderError(f"千问返回的分镜格式不正确：{exc}") from exc
