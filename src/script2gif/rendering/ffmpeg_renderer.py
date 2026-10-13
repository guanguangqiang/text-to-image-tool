from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Callable, Optional

from script2gif.domain.enums import MotionType, ProjectStatus
from script2gif.domain.errors import RenderError
from script2gif.domain.models import Project, Shot
from script2gif.infrastructure.project_store import LocalProjectStore
from script2gif.rendering.subtitle import SubtitleOverlayRenderer

RenderProgress = Callable[[int, int, str], None]


class FFmpegRenderer:
    def __init__(self, store: LocalProjectStore, ffmpeg_path: str = "") -> None:
        self.store = store
        self.ffmpeg = self._find_ffmpeg(ffmpeg_path)
        self.subtitle_renderer = SubtitleOverlayRenderer()

    def render_project(
        self,
        project_dir: Path,
        project: Project,
        progress: Optional[RenderProgress] = None,
    ) -> tuple[Path, Path]:
        usable = [shot for shot in project.shots if shot.keyframe_path]
        if not usable:
            raise RenderError("没有可渲染的关键帧")
        project.status = ProjectStatus.RENDERING
        self.store.save(project_dir, project)
        render_dir = project_dir / "temp" / "render"
        render_dir.mkdir(parents=True, exist_ok=True)
        clips: list[Path] = []
        try:
            for current, shot in enumerate(usable, start=1):
                if progress:
                    progress(current, len(usable) + 2, f"正在渲染分镜 {shot.index}")
                clip = render_dir / f"{shot.index:04d}_{shot.id}.mp4"
                self.render_shot(project_dir, project, shot, clip)
                shot.video_path = clip.relative_to(project_dir).as_posix()
                clips.append(clip)
            mp4 = project_dir / "outputs" / "final.mp4"
            if progress:
                progress(len(usable) + 1, len(usable) + 2, "正在合并视频")
            self.concat(clips, mp4)
            gif = project_dir / "outputs" / "final.gif"
            if progress:
                progress(len(usable) + 2, len(usable) + 2, "正在导出 GIF")
            self.export_gif(mp4, gif, project.settings.gif_fps)
            for shot in usable:
                shot.video_path = None
            shutil.rmtree(render_dir, ignore_errors=True)
            project.status = ProjectStatus.SUCCEEDED
            self.store.save(project_dir, project)
            return mp4, gif
        except Exception:
            project.status = ProjectStatus.FAILED
            self.store.save(project_dir, project)
            raise

    def render_shot(
        self,
        project_dir: Path,
        project: Project,
        shot: Shot,
        destination: Path,
    ) -> Path:
        image_path = project.resolve(project_dir, shot.keyframe_path)
        if image_path is None or not image_path.exists():
            raise RenderError(f"分镜 {shot.index} 的关键帧不存在")
        width = project.settings.output_width
        height = project.settings.output_height
        fps = project.settings.video_fps
        frames = max(1, round(shot.duration_seconds * fps))
        motion_filter = self.motion_filter(shot.motion, width, height, fps, frames)
        command = [self.ffmpeg, "-y", "-loop", "1", "-i", str(image_path)]
        subtitle_path: Optional[Path] = None
        if shot.subtitle:
            subtitle_path = destination.with_suffix(".subtitle.png")
            self.subtitle_renderer.render(shot.subtitle, width, height, subtitle_path)
            command.extend(["-loop", "1", "-i", str(subtitle_path)])
            video_filter = (
                f"[0:v]{motion_filter}[motion];"
                "[1:v]format=rgba[subtitle];"
                "[motion][subtitle]overlay=0:0:format=auto,format=yuv420p[out]"
            )
            command.extend(["-filter_complex", video_filter, "-map", "[out]"])
        else:
            command.extend(["-vf", f"{motion_filter},format=yuv420p"])
        command.extend(
            [
                "-t",
                f"{shot.duration_seconds:.3f}",
                "-r",
                str(fps),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-movflags",
                "+faststart",
                str(destination),
            ]
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._run(command)
        finally:
            if subtitle_path:
                subtitle_path.unlink(missing_ok=True)
        return destination

    def concat(self, clips: Sequence[Path], destination: Path) -> Path:
        if not clips:
            raise RenderError("没有可合并的视频片段")
        manifest = destination.parent / ".concat.txt"
        destination.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"file '{self._concat_escape(path.resolve())}'" for path in clips]
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            self._run(
                [
                    self.ffmpeg,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(manifest),
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(destination),
                ]
            )
        finally:
            manifest.unlink(missing_ok=True)
        return destination

    def export_gif(self, source: Path, destination: Path, fps: int = 12) -> Path:
        filter_complex = (
            f"[0:v]fps={fps},scale='min(720,iw)':-2:flags=lanczos,split[a][b];"
            "[a]palettegen=max_colors=192[p];[b][p]paletteuse=dither=sierra2_4a"
        )
        self._run(
            [
                self.ffmpeg,
                "-y",
                "-i",
                str(source),
                "-filter_complex",
                filter_complex,
                "-loop",
                "0",
                str(destination),
            ]
        )
        return destination

    @staticmethod
    def motion_filter(
        motion: MotionType,
        width: int,
        height: int,
        fps: int,
        frames: int,
    ) -> str:
        base = (
            f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
            f"crop={width * 2}:{height * 2}"
        )
        progress = f"on/{max(frames - 1, 1)}"
        if motion == MotionType.STATIC:
            zoom, x, y = "1.0", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        elif motion == MotionType.ZOOM_OUT:
            zoom, x, y = f"1.12-0.12*{progress}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        elif motion == MotionType.PAN_LEFT:
            zoom, x, y = "1.12", f"(iw-iw/zoom)*(1-{progress})", "ih/2-(ih/zoom/2)"
        elif motion == MotionType.PAN_RIGHT:
            zoom, x, y = "1.12", f"(iw-iw/zoom)*{progress}", "ih/2-(ih/zoom/2)"
        elif motion == MotionType.PAN_UP:
            zoom, x, y = "1.12", "iw/2-(iw/zoom/2)", f"(ih-ih/zoom)*(1-{progress})"
        elif motion == MotionType.PAN_DOWN:
            zoom, x, y = "1.12", "iw/2-(iw/zoom/2)", f"(ih-ih/zoom)*{progress}"
        else:
            zoom, x, y = f"1.0+0.12*{progress}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        return f"{base},zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:s={width}x{height}:fps={fps}"

    def _run(self, command: Sequence[str]) -> None:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip()[-3000:] or "FFmpeg 未返回错误详情"
            raise RenderError(f"FFmpeg 执行失败：{detail}")

    @staticmethod
    def _find_ffmpeg(configured: str) -> str:
        if configured:
            candidate = Path(configured)
            if candidate.exists():
                return str(candidate)
            raise RenderError(f"配置的 FFmpeg 不存在：{configured}")
        bundled_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).parents[3]))
        bundled = bundle_root / "resources" / "ffmpeg" / bundled_name
        if bundled.exists():
            return str(bundled)
        discovered = shutil.which("ffmpeg")
        if discovered:
            return discovered
        raise RenderError("没有找到 FFmpeg，请在设置中指定 ffmpeg.exe")

    @staticmethod
    def _concat_escape(path: Path) -> str:
        return str(path).replace("'", "'\\''")
