"""Renders the live glucose value onto the lemon Dock icon artwork.

Pure/PIL-only module: no AppKit/Foundation/PyObjCTools imports here, so it
stays importable in the normal dev venv (Pillow is a build-only dependency,
see requirements-build.txt).
"""
from dataclasses import dataclass
from typing import Literal, Optional

from PIL import Image, ImageDraw, ImageFont

# Fractional LCD-screen position/size, matching static/widget.html's
# #lemon-screen box (left/top/width/height percentages) against
# static/lemon.svg's 660x860 viewBox, applied to the base image's own
# dimensions so this works regardless of the base PNG's exact resolution.
SCREEN_LEFT_FRACTION = 0.2424
SCREEN_TOP_FRACTION = 0.3895
SCREEN_WIDTH_FRACTION = 0.5273
SCREEN_HEIGHT_FRACTION = 0.2279

# Texas orange (0xBF5700) - matches static/index.html's/widget.html's
# statusColor() (see tests/test_status_color.py), which replaced the plain
# CSS orange keyword for its poor contrast against the LCD screen.
COLOR_HIGH = (191, 87, 0)
COLOR_LOW = (255, 0, 0)
COLOR_IN_RANGE = (0, 128, 0)
COLOR_NO_DATA = (0, 0, 0)

RangeStatus = Literal["high", "low", "in-range"]


def range_status(value: float, target_low: int, target_high: int) -> RangeStatus:
    """Mirrors app/libre_client.py's derivation exactly: never trust API flags."""
    if value > target_high:
        return "high"
    if value < target_low:
        return "low"
    return "in-range"


@dataclass
class IconRenderSpec:
    text: str
    status: Optional[RangeStatus]  # None when text == "--"


def render_spec(
    value: Optional[float],
    target_low: Optional[int],
    target_high: Optional[int],
    error: Optional[str],
) -> IconRenderSpec:
    if error is not None or value is None or target_low is None or target_high is None:
        return IconRenderSpec(text="--", status=None)
    return IconRenderSpec(
        text=str(round(value)),
        status=range_status(value, target_low, target_high),
    )


def _status_color(status: Optional[RangeStatus]) -> tuple[int, int, int]:
    if status == "high":
        return COLOR_HIGH
    if status == "low":
        return COLOR_LOW
    if status == "in-range":
        return COLOR_IN_RANGE
    return COLOR_NO_DATA


def render_icon(spec: IconRenderSpec, base_image_path, font_path) -> Image.Image:
    """Draws spec.text centered on the lemon's existing LCD screen artwork.

    The base image already bakes in the LCD screen's rounded-rect look (from
    static/lemon.svg), so - matching how static/widget.html overlays digits
    directly on top of that same artwork with no separate background fill -
    this only draws the text, not a new background rectangle.

    base_image_path/font_path are taken as explicit arguments (rather than
    resolved internally) so tests can point at small fixture files instead of
    the real bundled assets.
    """
    base = Image.open(base_image_path).convert("RGBA")
    width, height = base.size

    screen_x = SCREEN_LEFT_FRACTION * width
    screen_y = SCREEN_TOP_FRACTION * height
    screen_w = SCREEN_WIDTH_FRACTION * width
    screen_h = SCREEN_HEIGHT_FRACTION * height

    draw = ImageDraw.Draw(base)
    font_size = max(1, int(screen_h * 0.8))
    font = ImageFont.truetype(font_path, font_size)
    color = _status_color(spec.status)

    bbox = draw.textbbox((0, 0), spec.text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = screen_x + (screen_w - text_w) / 2 - bbox[0]
    text_y = screen_y + (screen_h - text_h) / 2 - bbox[1]

    draw.text((text_x, text_y), spec.text, font=font, fill=color)

    return base


def pad_to_square(image: Image.Image) -> Image.Image:
    """Centers image on a transparent square canvas.

    macOS Dock tiles are always square; NSApplication.setApplicationIconImage_
    stretches a non-square NSImage to fill that square instead of
    letterboxing it, which visibly distorts lemon.svg's portrait (660x860)
    aspect ratio. Padding to square here - rather than reshaping the base
    artwork - keeps render_icon's output matching the base image's own
    aspect ratio (simpler to reason about/test) while still handing AppKit
    something that won't be stretched.
    """
    width, height = image.size
    side = max(width, height)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(image, ((side - width) // 2, (side - height) // 2), image)
    return square
