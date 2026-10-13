from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

from script2gif.domain.errors import RenderError


class SubtitleOverlayRenderer:
    def render(self, text: str, width: int, height: int, output: Path) -> Path:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as exc:
            raise RenderError("缺少 Pillow，无法绘制字幕") from exc

        output.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        font_size = max(22, int(height * 0.045))
        font = self._font(ImageFont, font_size)
        lines = self._wrap(draw, text, font, int(width * 0.84))
        spacing = max(6, font_size // 4)
        boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
        line_heights = [box[3] - box[1] for box in boxes]
        block_height = sum(line_heights) + spacing * max(0, len(lines) - 1)
        y = int(height * 0.88) - block_height
        padding_x = max(16, font_size // 2)
        padding_y = max(10, font_size // 3)
        max_width = max((box[2] - box[0] for box in boxes), default=0)
        background = (
            (width - max_width) // 2 - padding_x,
            y - padding_y,
            (width + max_width) // 2 + padding_x,
            y + block_height + padding_y,
        )
        draw.rounded_rectangle(background, radius=12, fill=(0, 0, 0, 145))
        for line, box, line_height in zip(lines, boxes, line_heights):
            line_width = box[2] - box[0]
            draw.text(
                ((width - line_width) // 2, y),
                line,
                font=font,
                fill=(255, 255, 255, 255),
                stroke_width=1,
                stroke_fill=(0, 0, 0, 220),
            )
            y += line_height + spacing
        temporary = output.with_suffix(".tmp.png")
        image.save(temporary, format="PNG")
        temporary.replace(output)
        return output

    def _font(self, image_font: object, size: int):
        for candidate in self._font_candidates():
            if candidate.exists():
                return image_font.truetype(str(candidate), size=size)
        return image_font.load_default()

    def _font_candidates(self) -> Iterable[Path]:
        if sys.platform == "win32":
            yield Path("C:/Windows/Fonts/msyh.ttc")
            yield Path("C:/Windows/Fonts/simhei.ttf")
        elif sys.platform == "darwin":
            yield Path("/System/Library/Fonts/PingFang.ttc")
            yield Path("/System/Library/Fonts/STHeiti Medium.ttc")
        else:
            yield Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")

    @staticmethod
    def _wrap(draw: object, text: str, font: object, max_width: int) -> list[str]:
        lines: list[str] = []
        current = ""
        for char in text.strip():
            candidate = current + char
            width = draw.textbbox((0, 0), candidate, font=font)[2]
            if current and width > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines or [""]
