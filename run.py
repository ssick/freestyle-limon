"""Entry point for the standalone macOS app (see `pyinstaller` build in README)."""
import io
import socket
import sys
import threading
from pathlib import Path

import AppKit
import Foundation
import uvicorn
import webview
from PyObjCTools import AppHelper

from app import state
from app.dock_icon_render import blink_alpha, pad_to_square, render_icon, render_spec
from app.main import app

HOST = "127.0.0.1"

WIDGET_WIDTH = 180
WIDGET_HEIGHT = 180
WIDGET_MARGIN = 24

DOCK_ICON_UPDATE_INTERVAL_SECONDS = 45
# Matches static/index.html's/widget.html's RETRY_INTERVAL_MS: poll fast until
# the first successful reading lands, instead of waiting a full interval.
DOCK_ICON_RETRY_INTERVAL_SECONDS = 2
# Matches static/index.html's/widget.html's lcd-blink @keyframes half-cycle
# (1s animation, two phases): ticking the icon this often is what makes it
# visibly blink while stale.
DOCK_ICON_BLINK_INTERVAL_SECONDS = 0.5

_dock_icon_has_reading = False
_dock_icon_blink_on = True

# Bundled data files (datas=[...] in freestyle-limon.spec) land in
# Contents/Resources/ in a PyInstaller macOS app bundle, not next to the
# executable in Contents/MacOS/ (unlike .env, which is an external file the
# user drops next to the .app - see the path-walking comment at the top of
# app/main.py).
if getattr(sys, "frozen", False):
    ASSETS_DIR = Path(sys.executable).resolve().parent.parent / "Resources"
else:
    ASSETS_DIR = Path(__file__).resolve().parent

DOCK_ICON_BASE_IMAGE_PATH = ASSETS_DIR / "packaging" / "lemon-icon-base.png"
DOCK_ICON_FONT_PATH = ASSETS_DIR / "static" / "fonts" / "DSEG7Classic-Bold.ttf"


def _update_dock_icon() -> None:
    global _dock_icon_has_reading, _dock_icon_blink_on

    reading = state.get_latest()
    target_low, target_high = state.get_target_range()
    spec = render_spec(
        reading.value if reading is not None else None,
        target_low,
        target_high,
        state.get_error(),
    )
    if reading is not None:
        _dock_icon_has_reading = True

    is_stale = state.get_is_stale()
    _dock_icon_blink_on = (not _dock_icon_blink_on) if is_stale else True
    alpha = blink_alpha(is_stale, _dock_icon_blink_on)
    pil_image = pad_to_square(render_icon(spec, DOCK_ICON_BASE_IMAGE_PATH, DOCK_ICON_FONT_PATH, alpha=alpha))

    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    ns_data = Foundation.NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
    ns_image = AppKit.NSImage.alloc().initWithData_(ns_data)
    AppKit.NSApplication.sharedApplication().setApplicationIconImage_(ns_image)

    if is_stale:
        interval = DOCK_ICON_BLINK_INTERVAL_SECONDS
    else:
        interval = DOCK_ICON_UPDATE_INTERVAL_SECONDS if _dock_icon_has_reading else DOCK_ICON_RETRY_INTERVAL_SECONDS
    AppHelper.callLater(interval, _update_dock_icon)


def _run_server(sock: socket.socket) -> None:
    config = uvicorn.Config(app, host=HOST, log_level="warning")
    uvicorn.Server(config).run(sockets=[sock])


class WidgetApi:
    """Exposed to the dashboard page as `window.pywebview.api`."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self.widget_window: webview.Window | None = None

    def toggle_widget(self) -> bool:
        """Open the widget window if closed, close it if open. Returns the new open state."""
        if self.widget_window is not None:
            self.widget_window.destroy()
            return False
        self._open_widget()
        return True

    def is_widget_open(self) -> bool:
        return self.widget_window is not None

    def _open_widget(self) -> None:
        x, y = self._default_widget_position()
        self.widget_window = webview.create_window(
            "Freestyle Limón Widget",
            f"{self._base_url}/static/widget.html",
            width=WIDGET_WIDTH,
            height=WIDGET_HEIGHT,
            x=x,
            y=y,
            frameless=True,
            easy_drag=True,
            on_top=True,
            transparent=True,
            resizable=False,
            shadow=False,
            background_color="#FFFDF3",
        )
        self.widget_window.events.closed += self._on_widget_closed

    def _on_widget_closed(self) -> None:
        self.widget_window = None

    def _default_widget_position(self) -> tuple[int, int]:
        try:
            screen = webview.screens()[0]
            return (
                int(screen.x + screen.width - WIDGET_WIDTH - WIDGET_MARGIN),
                int(screen.y + WIDGET_MARGIN),
            )
        except Exception:
            return WIDGET_MARGIN, WIDGET_MARGIN


if __name__ == "__main__":
    # Bind to a random free port instead of a fixed one, so the app doesn't
    # clash with anything else already listening on a well-known port.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, 0))
    port = sock.getsockname()[1]
    sock.listen()

    threading.Thread(target=_run_server, args=(sock,), daemon=True).start()
    base_url = f"http://{HOST}:{port}"
    widget_api = WidgetApi(base_url)
    webview.create_window(
        "Freestyle Limón",
        base_url,
        width=480,
        height=800,
        min_size=(360, 600),
        js_api=widget_api,
    )
    _update_dock_icon()
    webview.start(gui="cocoa")
