"""Entry point for the standalone macOS app (see `pyinstaller` build in README)."""
import socket
import threading

import uvicorn
import webview

from app.main import app

HOST = "127.0.0.1"

WIDGET_WIDTH = 180
WIDGET_HEIGHT = 180
WIDGET_MARGIN = 24


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
    webview.start(gui="cocoa")
