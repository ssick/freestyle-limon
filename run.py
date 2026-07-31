"""Entry point for the standalone macOS app (see `pyinstaller` build in README)."""
import socket
import threading

import AppKit
import uvicorn
import webview
from PyObjCTools import AppHelper

from app.main import app

HOST = "127.0.0.1"

WIDGET_WIDTH = 180
WIDGET_HEIGHT = 180
WIDGET_MARGIN = 24

DOCK_BADGE_UPDATE_INTERVAL_SECONDS = 45
# Matches static/index.html's/widget.html's RETRY_INTERVAL_MS: poll fast until
# the first successful reading lands, instead of waiting a full interval.
DOCK_BADGE_RETRY_INTERVAL_SECONDS = 2

_dock_badge_has_reading = False


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


def _update_dock_badge():
    global _dock_badge_has_reading

    from app import state
    from app.dock_badge import badge_text

    reading = state.get_latest()
    value = reading.value if reading is not None else None
    if reading is not None:
        _dock_badge_has_reading = True
    text = badge_text(value, state.get_error())
    AppKit.NSApplication.sharedApplication().dockTile().setBadgeLabel_(text)
    AppKit.NSApplication.sharedApplication().dockTile().display()

    interval = DOCK_BADGE_UPDATE_INTERVAL_SECONDS if _dock_badge_has_reading else DOCK_BADGE_RETRY_INTERVAL_SECONDS
    AppHelper.callLater(interval, _update_dock_badge)


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
    _update_dock_badge()
    webview.start(gui="cocoa")
