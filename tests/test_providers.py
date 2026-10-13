import json

import httpx

from script2gif.providers.protocols import ImageRequest
from script2gif.providers.wan_image import WanImageProvider


def test_wan_provider_submits_and_parses_async_task() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["model"] == "wan2.7-image-pro"
            assert payload["parameters"]["size"] == "2048*1152"
            assert request.headers["X-DashScope-Async"] == "enable"
            return httpx.Response(200, json={"output": {"task_id": "task-123"}})
        return httpx.Response(
            200,
            json={
                "output": {
                    "task_status": "SUCCEEDED",
                    "choices": [
                        {"message": {"content": [{"image": "https://example.com/result.png"}]}}
                    ],
                }
            },
        )

    provider = WanImageProvider("secret", "https://workspace.example")
    provider._client.close()
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        task_id = provider.submit(ImageRequest(prompt="森林中的狐狸", size="2048*1152"))
        task = provider.get_task(task_id)
    finally:
        provider.close()

    assert task_id == "task-123"
    assert task.status == "SUCCEEDED"
    assert task.result_url == "https://example.com/result.png"
    assert calls == [
        "/api/v1/services/aigc/image-generation/generation",
        "/api/v1/tasks/task-123",
    ]
