from script2gif.domain.enums import MotionType
from script2gif.rendering.ffmpeg_renderer import FFmpegRenderer


def test_motion_filter_contains_requested_output_size() -> None:
    result = FFmpegRenderer.motion_filter(MotionType.ZOOM_IN, 1280, 720, 24, 96)

    assert "s=1280x720" in result
    assert "fps=24" in result
    assert "zoompan" in result


def test_pan_motion_changes_horizontal_position() -> None:
    result = FFmpegRenderer.motion_filter(MotionType.PAN_RIGHT, 720, 1280, 24, 72)

    assert "(iw-iw/zoom)*on/71" in result
