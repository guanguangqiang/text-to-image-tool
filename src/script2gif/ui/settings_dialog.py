from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from script2gif.domain.models import AppSettings
from script2gif.infrastructure.credential_store import CredentialStore
from script2gif.infrastructure.settings_store import SettingsStore


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: AppSettings,
        settings_store: SettingsStore,
        credential_store: CredentialStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(560)
        self.settings = settings
        self.settings_store = settings_store
        self.credential_store = credential_store

        self.workspace_id = QLineEdit(settings.workspace_id)
        self.workspace_id.setPlaceholderText("阿里云百炼业务空间 Workspace ID")
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("留空表示不修改，密钥仅保存到系统凭据管理器")
        self.qwen_model = QLineEdit(settings.qwen_model)
        self.image_model = QLineEdit(settings.image_model)
        self.ffmpeg_path = QLineEdit(settings.ffmpeg_path)
        browse = QPushButton("选择…")
        browse.clicked.connect(self._browse_ffmpeg)
        ffmpeg_row = QHBoxLayout()
        ffmpeg_row.addWidget(self.ffmpeg_path)
        ffmpeg_row.addWidget(browse)
        self.cache_limit = QSpinBox()
        self.cache_limit.setRange(1, 100)
        self.cache_limit.setValue(round(settings.cache_limit_gb))
        self.cache_limit.setSuffix(" GB")

        form = QFormLayout()
        form.addRow("Workspace ID", self.workspace_id)
        form.addRow("API Key", self.api_key)
        form.addRow("分镜模型", self.qwen_model)
        form.addRow("图片模型", self.image_model)
        form.addRow("FFmpeg", ffmpeg_row)
        form.addRow("缓存上限", self.cache_limit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 FFmpeg")
        if path:
            self.ffmpeg_path.setText(path)

    def _save(self) -> None:
        self.settings.workspace_id = self.workspace_id.text().strip()
        self.settings.qwen_model = self.qwen_model.text().strip() or "qwen3.8-flash"
        self.settings.image_model = self.image_model.text().strip() or "wan2.7-image-pro"
        self.settings.ffmpeg_path = self.ffmpeg_path.text().strip()
        self.settings.cache_limit_gb = float(self.cache_limit.value())
        api_key = self.api_key.text().strip()
        if api_key:
            self.credential_store.save_api_key(api_key)
        self.settings_store.save(self.settings)
        self.accept()
