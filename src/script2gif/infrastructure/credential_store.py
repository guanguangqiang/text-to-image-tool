import os
from typing import Optional

from script2gif.domain.errors import ConfigurationError


class CredentialStore:
    SERVICE_NAME = "Script2Gif"
    USERNAME = "aliyun_api_key"

    def get_api_key(self) -> Optional[str]:
        environment_value = os.environ.get("DASHSCOPE_API_KEY")
        if environment_value:
            return environment_value.strip()
        try:
            import keyring

            return keyring.get_password(self.SERVICE_NAME, self.USERNAME)
        except Exception:
            return None

    def require_api_key(self) -> str:
        value = self.get_api_key()
        if not value:
            raise ConfigurationError("请先在设置中保存阿里云百炼 API Key")
        return value

    def save_api_key(self, api_key: str) -> None:
        value = api_key.strip()
        if not value:
            raise ConfigurationError("API Key 不能为空")
        try:
            import keyring

            keyring.set_password(self.SERVICE_NAME, self.USERNAME, value)
        except Exception as exc:
            raise ConfigurationError(f"无法写入系统凭据管理器：{exc}") from exc

    def delete_api_key(self) -> None:
        try:
            import keyring

            keyring.delete_password(self.SERVICE_NAME, self.USERNAME)
        except Exception:
            return
