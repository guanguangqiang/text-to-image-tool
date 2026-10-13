from __future__ import annotations

import base64
import mimetypes
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from script2gif.domain.errors import ProviderError
from script2gif.providers.protocols import ImageRequest, RemoteTask


class WanImageProvider:
    def __init__(self, api_key: str, api_base_url: str) -> None:
        if not api_base_url:
            raise ProviderError("缺少百炼 Workspace ID，无法构造接口地址")
        self._api_base_url = api_base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=20.0),
            headers={"Authorization": f"Bearer {api_key}"},
        )

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=8),
        reraise=True,
    )
    def submit(self, request: ImageRequest) -> str:
        content: list[Dict[str, str]] = []
        for path in request.reference_images:
            content.append({"image": self._as_data_url(path)})
        content.append({"text": request.prompt})
        payload = {
            "model": request.model,
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": {
                "size": request.size,
                "n": 1,
                "watermark": False,
                "thinking_mode": True,
            },
        }
        response = self._client.post(
            f"{self._api_base_url}/api/v1/services/aigc/image-generation/generation",
            headers={"Content-Type": "application/json", "X-DashScope-Async": "enable"},
            json=payload,
        )
        data = self._response_json(response)
        task_id = self._dig(data, "output", "task_id")
        if not task_id:
            raise ProviderError(f"万相没有返回任务 ID：{data}")
        return str(task_id)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=8),
        reraise=True,
    )
    def get_task(self, task_id: str) -> RemoteTask:
        response = self._client.get(f"{self._api_base_url}/api/v1/tasks/{task_id}")
        data = self._response_json(response)
        output = data.get("output") or {}
        status = str(output.get("task_status") or output.get("status") or "UNKNOWN").upper()
        result_url = self._find_result_url(output)
        error = output.get("message") or output.get("task_metrics", {}).get("failed_reason")
        return RemoteTask(id=task_id, status=status, result_url=result_url, error=error)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=8),
        reraise=True,
    )
    def download(self, url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(f"{destination.suffix}.download")
        try:
            with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as response:
                response.raise_for_status()
                with temporary.open("wb") as stream:
                    for chunk in response.iter_bytes():
                        stream.write(chunk)
            temporary.replace(destination)
            return destination
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            if isinstance(exc, httpx.HTTPError):
                raise
            raise ProviderError(f"下载生成图片失败：{exc}") from exc

    def close(self) -> None:
        self._client.close()

    def _response_json(self, response: httpx.Response) -> Dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(f"模型接口返回了无效响应（HTTP {response.status_code}）") from exc
        if response.is_error:
            message = data.get("message") or data.get("code") or response.reason_phrase
            raise ProviderError(f"模型接口请求失败（HTTP {response.status_code}）：{message}")
        return data

    def _as_data_url(self, path: Path) -> str:
        if not path.exists():
            raise ProviderError(f"参考图不存在：{path}")
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _find_result_url(self, output: Dict[str, Any]) -> Optional[str]:
        direct = output.get("url") or output.get("result_url")
        if direct:
            return str(direct)
        for key in ("results", "choices"):
            values = output.get(key) or []
            for value in self._iter_dicts(values):
                candidate = value.get("url") or value.get("image_url")
                if candidate:
                    return str(candidate)
                content = value.get("message", {}).get("content", [])
                for item in self._iter_dicts(content):
                    candidate = item.get("image") or item.get("url")
                    if candidate:
                        return str(candidate)
        return None

    @staticmethod
    def _iter_dicts(values: Iterable[Any]) -> Iterable[Dict[str, Any]]:
        return (value for value in values if isinstance(value, dict))

    @staticmethod
    def _dig(value: Dict[str, Any], *keys: str) -> Any:
        current: Any = value
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current
