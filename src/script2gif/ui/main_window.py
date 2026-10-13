from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThreadPool, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from script2gif.application.generation_service import ImageGenerationService
from script2gif.application.project_service import ProjectService
from script2gif.application.storyboard_service import StoryboardService
from script2gif.domain.enums import MotionType, ShotStatus, TaskStatus
from script2gif.domain.errors import ConfigurationError
from script2gif.domain.models import Project, Shot
from script2gif.infrastructure.app_paths import AppPaths
from script2gif.infrastructure.cache_store import CacheStore
from script2gif.infrastructure.credential_store import CredentialStore
from script2gif.infrastructure.project_store import LocalProjectStore
from script2gif.infrastructure.settings_store import SettingsStore
from script2gif.jobs.worker import FunctionWorker
from script2gif.providers.qwen_planner import QwenStoryboardPlanner
from script2gif.providers.wan_image import WanImageProvider
from script2gif.rendering.ffmpeg_renderer import FFmpegRenderer
from script2gif.ui.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    HEADERS = ["序号", "场景", "动作", "镜头", "时长", "运镜", "字幕", "生图提示词", "状态"]
    IMAGE_SIZES = {
        "16:9": "2048*1152",
        "9:16": "1152*2048",
        "1:1": "2048*2048",
        "4:3": "2048*1536",
        "3:4": "1536*2048",
    }

    def __init__(self, app_paths: AppPaths) -> None:
        super().__init__()
        self.app_paths = app_paths
        self.store = LocalProjectStore()
        self.project_service = ProjectService(self.store)
        self.storyboard_service = StoryboardService(self.store)
        self.settings_store = SettingsStore(app_paths.config_dir)
        self.credentials = CredentialStore()
        self.settings = self.settings_store.load()
        self.cache = CacheStore(app_paths.cache_dir / "generations")
        self.image_service = ImageGenerationService(self.store, self.cache)
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: set[FunctionWorker] = set()
        self.project_dir: Optional[Path] = None
        self.project: Optional[Project] = None
        self._dirty = False
        self._table_loading = False

        self.setWindowTitle("Script2Gif - 剧本转动态 GIF")
        self.resize(1280, 820)
        self._build_toolbar()
        self._build_ui()
        self.statusBar().showMessage("请新建或打开项目")

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("项目")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        actions = [
            ("新建项目", self.new_project),
            ("打开项目", self.open_project),
            ("保存", self.save_project),
            ("打开项目目录", self.open_project_directory),
            ("设置", self.open_settings),
        ]
        for title, handler in actions:
            action = QAction(title, self)
            action.triggered.connect(handler)
            toolbar.addAction(action)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        self.project_label = QLabel("未打开项目")
        self.project_label.setStyleSheet("font-weight: 600; padding: 6px;")
        root.addWidget(self.project_label)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._script_page(), "1. 剧本")
        self.tabs.addTab(self._storyboard_page(), "2. 分镜")
        self.tabs.addTab(self._characters_page(), "3. 角色素材")
        self.tabs.addTab(self._generation_page(), "4. 生成")
        self.tabs.addTab(self._export_page(), "5. 导出")
        root.addWidget(self.tabs)
        self.setCentralWidget(central)

    def _script_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.style_edit = QLineEdit("电影感插画")
        self.style_edit.textChanged.connect(self._mark_dirty)
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(["16:9", "9:16", "1:1", "4:3", "3:4"])
        self.aspect_combo.currentTextChanged.connect(self._mark_dirty)
        form.addRow("统一画风", self.style_edit)
        form.addRow("画面比例", self.aspect_combo)
        layout.addLayout(form)
        self.script_edit = QTextEdit()
        self.script_edit.setPlaceholderText("在这里输入或粘贴剧本……")
        self.script_edit.textChanged.connect(self._mark_dirty)
        layout.addWidget(self.script_edit, 1)
        row = QHBoxLayout()
        import_button = QPushButton("导入文本")
        import_button.clicked.connect(self.import_script)
        plan_button = QPushButton("使用千问生成分镜")
        plan_button.clicked.connect(self.generate_storyboard)
        row.addWidget(import_button)
        row.addStretch()
        row.addWidget(plan_button)
        layout.addLayout(row)
        return page

    def _storyboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.shot_table = QTableWidget(0, len(self.HEADERS))
        self.shot_table.setHorizontalHeaderLabels(self.HEADERS)
        self.shot_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.shot_table.horizontalHeader().setStretchLastSection(True)
        self.shot_table.setColumnWidth(0, 55)
        self.shot_table.setColumnWidth(1, 170)
        self.shot_table.setColumnWidth(2, 180)
        self.shot_table.setColumnWidth(3, 110)
        self.shot_table.setColumnWidth(4, 70)
        self.shot_table.setColumnWidth(5, 100)
        self.shot_table.setColumnWidth(6, 160)
        self.shot_table.setColumnWidth(7, 320)
        self.shot_table.itemChanged.connect(self._shot_changed)
        self.shot_table.itemDoubleClicked.connect(self._open_keyframe)
        layout.addWidget(self.shot_table)
        row = QHBoxLayout()
        add_button = QPushButton("增加分镜")
        add_button.clicked.connect(self.add_shot)
        remove_button = QPushButton("删除所选")
        remove_button.clicked.connect(self.remove_shot)
        row.addWidget(add_button)
        row.addWidget(remove_button)
        row.addStretch()
        layout.addLayout(row)
        return page

    def _characters_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.character_table = QTableWidget(0, 3)
        self.character_table.setHorizontalHeaderLabels(["角色", "外观设定", "参考图"])
        self.character_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.character_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.character_table)
        import_reference = QPushButton("为所选角色导入参考图")
        import_reference.clicked.connect(self.import_reference_image)
        layout.addWidget(import_reference)
        return page

    def _generation_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        help_label = QLabel(
            "确认分镜后批量生成关键帧。成功图片会保存到项目 assets/keyframes 目录，"
            "失败分镜可再次生成。"
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.generate_progress = QProgressBar()
        self.generate_progress.setRange(0, 100)
        layout.addWidget(self.generate_progress)
        self.generate_status = QLabel("尚未开始")
        layout.addWidget(self.generate_status)
        row = QHBoxLayout()
        generate = QPushButton("生成全部关键帧")
        generate.clicked.connect(self.generate_images)
        open_assets = QPushButton("打开关键帧目录")
        open_assets.clicked.connect(lambda: self._open_subdirectory("assets/keyframes"))
        row.addWidget(generate)
        row.addWidget(open_assets)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        return page

    def _export_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(320, 3840)
        self.width_spin.setValue(1280)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(240, 2160)
        self.height_spin.setValue(720)
        self.gif_fps_spin = QSpinBox()
        self.gif_fps_spin.setRange(5, 30)
        self.gif_fps_spin.setValue(12)
        form.addRow("输出宽度", self.width_spin)
        form.addRow("输出高度", self.height_spin)
        form.addRow("GIF 帧率", self.gif_fps_spin)
        layout.addLayout(form)
        self.render_progress = QProgressBar()
        self.render_progress.setRange(0, 100)
        layout.addWidget(self.render_progress)
        self.render_status = QLabel("先生成关键帧，再执行导出")
        layout.addWidget(self.render_status)
        row = QHBoxLayout()
        export = QPushButton("导出 MP4 和 GIF")
        export.clicked.connect(self.render_outputs)
        open_outputs = QPushButton("打开输出目录")
        open_outputs.clicked.connect(lambda: self._open_subdirectory("outputs"))
        row.addWidget(export)
        row.addWidget(open_outputs)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        return page

    def new_project(self) -> None:
        parent = QFileDialog.getExistingDirectory(self, "选择项目保存位置")
        if not parent:
            return
        name, accepted = QInputDialog.getText(self, "新建项目", "项目名称")
        if not accepted:
            return
        try:
            project_dir, project = self.project_service.create(Path(parent), name)
            self._set_project(project_dir, project, "")
        except Exception as exc:
            self._show_error("新建项目失败", exc)

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "", "Script2Gif 项目 (project.json)"
        )
        if not path:
            return
        try:
            project_dir, project, script = self.project_service.open(Path(path))
            self._set_project(project_dir, project, script)
            self._offer_resume_tasks()
        except Exception as exc:
            self._show_error("打开项目失败", exc)

    def save_project(self) -> None:
        if not self._require_project():
            return
        try:
            self._sync_form_to_project()
            self.project_service.save(
                self.project_dir, self.project, self.script_edit.toPlainText()
            )
            self._dirty = False
            self.statusBar().showMessage("项目已保存", 3000)
        except Exception as exc:
            self._show_error("保存失败", exc)

    def import_script(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入剧本", "", "文本文件 (*.txt *.md)")
        if path:
            try:
                self.script_edit.setPlainText(Path(path).read_text(encoding="utf-8"))
            except Exception as exc:
                self._show_error("导入失败", exc)

    def generate_storyboard(self) -> None:
        if not self._require_project():
            return
        script = self.script_edit.toPlainText().strip()
        if not script:
            QMessageBox.warning(self, "缺少剧本", "请先输入剧本内容。")
            return
        try:
            self._sync_form_to_project()
            planner = QwenStoryboardPlanner(
                self.credentials.require_api_key(),
                self.settings.compatible_base_url,
                self.settings.qwen_model,
            )
        except Exception as exc:
            self._show_error("配置不完整", exc)
            return
        worker = FunctionWorker(
            self.storyboard_service.generate,
            self.project_dir,
            self.project,
            script,
            planner,
        )
        worker.signals.succeeded.connect(self._storyboard_ready)
        self._start_worker(worker, "千问正在分析剧本并生成分镜……")

    def generate_images(self) -> None:
        if not self._require_project() or not self.project.shots:
            QMessageBox.warning(self, "没有分镜", "请先生成或添加分镜。")
            return
        self.save_project()
        try:
            api_key = self.credentials.require_api_key()
            if not self.settings.api_base_url:
                raise ConfigurationError("请先在设置中填写 Workspace ID")
        except Exception as exc:
            self._show_error("配置不完整", exc)
            return

        def run_generation(progress):
            provider = WanImageProvider(api_key, self.settings.api_base_url)
            try:
                return self.image_service.generate_all(
                    self.project_dir, self.project, provider, progress=progress
                )
            finally:
                provider.close()

        worker = FunctionWorker(run_generation, with_progress=True)
        worker.signals.progress.connect(self._generation_progress)
        worker.signals.succeeded.connect(self._images_ready)
        self._start_worker(worker, "正在提交图片生成任务……")

    def render_outputs(self) -> None:
        if not self._require_project():
            return
        self._sync_form_to_project()
        self.project.settings.output_width = self.width_spin.value()
        self.project.settings.output_height = self.height_spin.value()
        self.project.settings.gif_fps = self.gif_fps_spin.value()
        self.store.save(self.project_dir, self.project)
        try:
            renderer = FFmpegRenderer(self.store, self.settings.ffmpeg_path)
        except Exception as exc:
            self._show_error("无法启动渲染器", exc)
            return
        worker = FunctionWorker(
            renderer.render_project,
            self.project_dir,
            self.project,
            with_progress=True,
        )
        worker.signals.progress.connect(self._render_progress)
        worker.signals.succeeded.connect(self._render_ready)
        self._start_worker(worker, "正在准备渲染……")

    def add_shot(self) -> None:
        if not self._require_project():
            return
        index = len(self.project.shots) + 1
        self.project.shots.append(
            Shot(
                index=index,
                scene="新场景",
                action="描述角色动作",
                camera="中景",
                image_prompt="描述画面主体、环境、构图和光线",
            )
        )
        self._populate_shots()
        self._mark_dirty()

    def remove_shot(self) -> None:
        if not self._require_project():
            return
        rows = sorted({index.row() for index in self.shot_table.selectedIndexes()}, reverse=True)
        for row in rows:
            if 0 <= row < len(self.project.shots):
                self.project.shots.pop(row)
        for index, shot in enumerate(self.project.shots, start=1):
            shot.index = index
        self._populate_shots()
        self._mark_dirty()

    def import_reference_image(self) -> None:
        if not self._require_project():
            return
        row = self.character_table.currentRow()
        if row < 0 or row >= len(self.project.characters):
            QMessageBox.information(self, "选择角色", "请先选择一个角色。")
            return
        source, _ = QFileDialog.getOpenFileName(
            self, "选择角色参考图", "", "图片 (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not source:
            return
        character = self.project.characters[row]
        destination = (
            self.project_dir
            / "assets"
            / "references"
            / f"{character.id}_{len(character.reference_images) + 1}{Path(source).suffix.lower()}"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        character.reference_images.append(destination.relative_to(self.project_dir).as_posix())
        self.store.save(self.project_dir, self.project)
        self._populate_characters()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.settings_store, self.credentials, parent=self)
        if dialog.exec():
            self.settings = self.settings_store.load()
            self.statusBar().showMessage("设置已保存", 3000)

    def _offer_resume_tasks(self) -> None:
        if not self.project:
            return
        running = [task for task in self.project.tasks if task.status == TaskStatus.RUNNING]
        if not running:
            return
        answer = QMessageBox.question(
            self,
            "恢复生成任务",
            f"发现 {len(running)} 个未完成的云端任务，是否继续等待并下载结果？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            api_key = self.credentials.require_api_key()
            if not self.settings.api_base_url:
                raise ConfigurationError("请先在设置中填写 Workspace ID")
        except Exception as exc:
            self._show_error("无法恢复任务", exc)
            return

        def resume():
            provider = WanImageProvider(api_key, self.settings.api_base_url)
            try:
                return self.image_service.resume_pending(self.project_dir, self.project, provider)
            finally:
                provider.close()

        worker = FunctionWorker(resume)
        worker.signals.succeeded.connect(self._resume_ready)
        self._start_worker(worker, "正在恢复未完成的生成任务……")

    def open_project_directory(self) -> None:
        if self._require_project():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project_dir)))

    def _open_subdirectory(self, relative: str) -> None:
        if not self._require_project():
            return
        path = self.project_dir / relative
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _set_project(self, project_dir: Path, project: Project, script: str) -> None:
        self.project_dir = project_dir
        self.project = project
        self.project_label.setText(f"{project.name}  ·  {project_dir}")
        self._table_loading = True
        self.script_edit.setPlainText(script)
        self.style_edit.setText(project.style)
        self.aspect_combo.setCurrentText(project.settings.aspect_ratio)
        self.width_spin.setValue(project.settings.output_width)
        self.height_spin.setValue(project.settings.output_height)
        self.gif_fps_spin.setValue(project.settings.gif_fps)
        self._table_loading = False
        self._populate_shots()
        self._populate_characters()
        self._dirty = False
        self.statusBar().showMessage(f"已打开项目：{project.name}", 3000)

    def _populate_shots(self) -> None:
        self._table_loading = True
        shots = self.project.shots if self.project else []
        self.shot_table.setRowCount(len(shots))
        for row, shot in enumerate(shots):
            values = [
                str(shot.index),
                shot.scene,
                shot.action,
                shot.camera,
                str(shot.duration_seconds),
                shot.motion.value,
                shot.subtitle or "",
                shot.image_prompt,
                shot.status.value,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {0, 8}:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.shot_table.setItem(row, column, item)
        self._table_loading = False

    def _populate_characters(self) -> None:
        characters = self.project.characters if self.project else []
        self.character_table.setRowCount(len(characters))
        for row, character in enumerate(characters):
            self.character_table.setItem(row, 0, QTableWidgetItem(character.name))
            self.character_table.setItem(row, 1, QTableWidgetItem(character.appearance))
            self.character_table.setItem(
                row, 2, QTableWidgetItem(f"{len(character.reference_images)} 张")
            )

    def _shot_changed(self, item: QTableWidgetItem) -> None:
        if self._table_loading or not self.project:
            return
        row = item.row()
        if row >= len(self.project.shots):
            return
        shot = self.project.shots[row]
        value = item.text().strip()
        try:
            if item.column() == 1:
                shot.scene = value
            elif item.column() == 2:
                shot.action = value
            elif item.column() == 3:
                shot.camera = value
            elif item.column() == 4:
                shot.duration_seconds = max(1.0, min(30.0, float(value)))
            elif item.column() == 5:
                shot.motion = MotionType(value)
            elif item.column() == 6:
                shot.subtitle = value or None
            elif item.column() == 7:
                shot.image_prompt = value
            self._mark_dirty()
        except (ValueError, TypeError) as exc:
            self.statusBar().showMessage(f"分镜字段无效：{exc}", 5000)
            self._populate_shots()

    def _open_keyframe(self, item: QTableWidgetItem) -> None:
        if not self.project or not self.project_dir:
            return
        shot = self.project.shots[item.row()]
        path = self.project.resolve(self.project_dir, shot.keyframe_path)
        if path and path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _sync_form_to_project(self) -> None:
        if not self.project:
            return
        self.project.style = self.style_edit.text().strip() or "电影感插画"
        self.project.settings.aspect_ratio = self.aspect_combo.currentText()
        self.project.settings.image_size = self.IMAGE_SIZES[self.aspect_combo.currentText()]
        self.project.settings.planner_model = self.settings.qwen_model
        self.project.settings.image_model = self.settings.image_model

    def _storyboard_ready(self, project: Project) -> None:
        self.project = project
        self.project_label.setText(f"{project.name}  ·  {self.project_dir}")
        self.style_edit.setText(project.style)
        self._populate_shots()
        self._populate_characters()
        self.tabs.setCurrentIndex(1)
        self.statusBar().showMessage(f"已生成 {len(project.shots)} 个分镜", 5000)

    def _images_ready(self, project: Project) -> None:
        self.project = project
        self._populate_shots()
        succeeded = sum(shot.status == ShotStatus.SUCCEEDED for shot in project.shots)
        self.generate_status.setText(f"完成：{succeeded}/{len(project.shots)} 个分镜")
        self.generate_progress.setValue(100)

    def _resume_ready(self, resumed: int) -> None:
        self._populate_shots()
        self.statusBar().showMessage(f"已恢复 {resumed} 个生成结果", 5000)

    def _render_ready(self, result: tuple[Path, Path]) -> None:
        mp4, gif = result
        self.render_progress.setValue(100)
        self.render_status.setText(f"已生成：{mp4.name}、{gif.name}")
        QMessageBox.information(self, "导出完成", f"MP4：{mp4}\nGIF：{gif}")

    def _generation_progress(self, current: int, total: int, message: str) -> None:
        self.generate_progress.setValue(round(current * 100 / max(total, 1)))
        self.generate_status.setText(message)

    def _render_progress(self, current: int, total: int, message: str) -> None:
        self.render_progress.setValue(round(current * 100 / max(total, 1)))
        self.render_status.setText(message)

    def _start_worker(self, worker: FunctionWorker, message: str) -> None:
        self._workers.add(worker)
        self.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.statusBar().showMessage(message)
        worker.signals.failed.connect(self._worker_failed)

        def finished() -> None:
            self._workers.discard(worker)
            self.setEnabled(True)
            QApplication.restoreOverrideCursor()

        worker.signals.finished.connect(finished)
        self.thread_pool.start(worker)

    def _worker_failed(self, message: str, traceback_text: str) -> None:
        logger.error("background_job_failed %s\n%s", message, traceback_text)
        QMessageBox.critical(self, "任务失败", message)
        self.statusBar().showMessage("任务失败", 5000)

    def _require_project(self) -> bool:
        if self.project is None or self.project_dir is None:
            QMessageBox.information(self, "没有项目", "请先新建或打开项目。")
            return False
        return True

    def _mark_dirty(self) -> None:
        if not self._table_loading:
            self._dirty = True

    def _show_error(self, title: str, error: Exception) -> None:
        logger.exception("%s: %s", title, error)
        QMessageBox.critical(self, title, str(error))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._dirty and self.project:
            answer = QMessageBox.question(
                self,
                "保存项目",
                "项目有未保存的更改，关闭前是否保存？",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Save:
                self.save_project()
        event.accept()
