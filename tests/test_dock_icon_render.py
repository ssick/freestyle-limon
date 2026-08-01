from pathlib import Path

import pytest

pytest.importorskip("PIL")

from app.dock_icon_render import IconRenderSpec, blink_alpha, range_status, render_spec  # noqa: E402

BASE_IMAGE_PATH = Path(__file__).resolve().parent.parent / "packaging" / "lemon-icon-base.png"
FONT_PATH = Path(__file__).resolve().parent.parent / "static" / "fonts" / "DSEG7Classic-Bold.ttf"


def test_range_status_exactly_at_target_low_is_in_range():
    assert range_status(70, target_low=70, target_high=180) == "in-range"


def test_range_status_exactly_at_target_high_is_in_range():
    assert range_status(180, target_low=70, target_high=180) == "in-range"


def test_range_status_just_above_target_high_is_high():
    assert range_status(180.1, target_low=70, target_high=180) == "high"


def test_range_status_just_below_target_low_is_low():
    assert range_status(69.9, target_low=70, target_high=180) == "low"


def test_render_spec_cold_start_all_none():
    spec = render_spec(value=None, target_low=None, target_high=None, error=None)
    assert spec == IconRenderSpec(text="--", status=None)


def test_render_spec_error_hides_cached_value():
    spec = render_spec(value=105.0, target_low=70, target_high=180, error="fetch failed")
    assert spec == IconRenderSpec(text="--", status=None)


def test_render_spec_high():
    spec = render_spec(value=220.0, target_low=70, target_high=180, error=None)
    assert spec == IconRenderSpec(text="220", status="high")


def test_render_spec_low():
    spec = render_spec(value=50.0, target_low=70, target_high=180, error=None)
    assert spec == IconRenderSpec(text="50", status="low")


def test_render_spec_in_range():
    spec = render_spec(value=100.0, target_low=70, target_high=180, error=None)
    assert spec == IconRenderSpec(text="100", status="in-range")


def test_render_spec_rounds_value():
    spec = render_spec(value=99.6, target_low=70, target_high=180, error=None)
    assert spec == IconRenderSpec(text="100", status="in-range")


def test_render_icon_matches_base_image_size_and_mode():
    from app.dock_icon_render import render_icon

    spec = IconRenderSpec(text="120", status="high")
    image = render_icon(spec, BASE_IMAGE_PATH, FONT_PATH)

    from PIL import Image

    base = Image.open(BASE_IMAGE_PATH)
    assert image.size == base.size
    assert image.mode == "RGBA"


def test_render_icon_status_colors_differ_in_screen_region():
    from app.dock_icon_render import (
        SCREEN_HEIGHT_FRACTION,
        SCREEN_LEFT_FRACTION,
        SCREEN_TOP_FRACTION,
        SCREEN_WIDTH_FRACTION,
        render_icon,
    )

    high_image = render_icon(IconRenderSpec(text="220", status="high"), BASE_IMAGE_PATH, FONT_PATH)
    low_image = render_icon(IconRenderSpec(text="220", status="low"), BASE_IMAGE_PATH, FONT_PATH)

    width, height = high_image.size
    x0 = int(SCREEN_LEFT_FRACTION * width)
    y0 = int(SCREEN_TOP_FRACTION * height)
    x1 = int(x0 + SCREEN_WIDTH_FRACTION * width)
    y1 = int(y0 + SCREEN_HEIGHT_FRACTION * height)

    high_pixels = set(high_image.crop((x0, y0, x1, y1)).getdata())
    low_pixels = set(low_image.crop((x0, y0, x1, y1)).getdata())

    assert high_pixels != low_pixels


def test_render_icon_no_data_uses_neutral_color_not_status_colors():
    from app.dock_icon_render import (
        COLOR_HIGH,
        COLOR_IN_RANGE,
        COLOR_LOW,
        SCREEN_HEIGHT_FRACTION,
        SCREEN_LEFT_FRACTION,
        SCREEN_TOP_FRACTION,
        SCREEN_WIDTH_FRACTION,
        render_icon,
    )

    image = render_icon(IconRenderSpec(text="--", status=None), BASE_IMAGE_PATH, FONT_PATH)

    width, height = image.size
    x0 = int(SCREEN_LEFT_FRACTION * width)
    y0 = int(SCREEN_TOP_FRACTION * height)
    x1 = int(x0 + SCREEN_WIDTH_FRACTION * width)
    y1 = int(y0 + SCREEN_HEIGHT_FRACTION * height)

    screen_pixels = set(image.crop((x0, y0, x1, y1)).getdata())
    for color in (COLOR_HIGH, COLOR_LOW, COLOR_IN_RANGE):
        assert (*color, 255) not in screen_pixels


def test_pad_to_square_centers_portrait_image_on_transparent_square():
    from PIL import Image

    from app.dock_icon_render import pad_to_square

    portrait = Image.new("RGBA", (660, 860), (255, 0, 0, 255))
    squared = pad_to_square(portrait)

    assert squared.size == (860, 860)
    assert squared.mode == "RGBA"
    # padding added on the sides (narrower dimension) is transparent
    assert squared.getpixel((10, 430))[3] == 0
    # original content is preserved, centered
    assert squared.getpixel((430, 430)) == (255, 0, 0, 255)


def test_pad_to_square_is_noop_for_already_square_image():
    from PIL import Image

    from app.dock_icon_render import pad_to_square

    square_in = Image.new("RGBA", (500, 500), (0, 255, 0, 255))
    squared = pad_to_square(square_in)

    assert squared.size == (500, 500)
    assert squared.getpixel((250, 250)) == (0, 255, 0, 255)


def test_blink_alpha_full_when_not_stale():
    assert blink_alpha(is_stale=False, blink_on=True) == 255
    assert blink_alpha(is_stale=False, blink_on=False) == 255


def test_blink_alpha_toggles_when_stale():
    from app.dock_icon_render import BLINK_DIM_ALPHA

    assert blink_alpha(is_stale=True, blink_on=True) == 255
    assert blink_alpha(is_stale=True, blink_on=False) == BLINK_DIM_ALPHA


def test_render_icon_dim_alpha_blends_toward_background_not_full_replace():
    from PIL import Image

    from app.dock_icon_render import BLINK_DIM_ALPHA, render_icon

    base = Image.open(BASE_IMAGE_PATH).convert("RGBA")
    spec = IconRenderSpec(text="120", status="high")
    dim_image = render_icon(spec, BASE_IMAGE_PATH, FONT_PATH, alpha=BLINK_DIM_ALPHA)

    base_pixels = list(base.getdata())
    dim_pixels = list(dim_image.getdata())
    # Restrict to pixels where the *background* was already fully opaque -
    # the base artwork's own antialiased screen-corner edges are legitimately
    # semi-transparent, so compositing over those can't reach exactly 255
    # and isn't what this test is checking.
    drawn_over_opaque_bg = [
        dim_pixels[i][3]
        for i in range(len(base_pixels))
        if dim_pixels[i] != base_pixels[i] and base_pixels[i][3] == 255
    ]

    assert drawn_over_opaque_bg, "expected render_icon to draw something over opaque background"
    # A plain pixel-replace bug would leave drawn pixels' own alpha at
    # BLINK_DIM_ALPHA, punching a semi-transparent hole in the dock icon;
    # correct RGBA blending keeps them fully opaque against the screen
    # artwork drawn underneath.
    assert all(alpha == 255 for alpha in drawn_over_opaque_bg)


def test_color_high_matches_frontend_texas_orange():
    """Drift guard: COLOR_HIGH must track statusColor()'s high color in
    static/index.html/widget.html (see tests/test_status_color.py). It's an
    RGB tuple rather than a CSS string, so that guard's text-based regex
    can't catch it if the frontend color changes again - this can."""
    from app.dock_icon_render import COLOR_HIGH

    assert COLOR_HIGH == (0xBF, 0x57, 0x00)
