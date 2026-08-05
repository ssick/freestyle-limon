"""Entry point for the standalone macOS app (see `pyinstaller` build in README)."""
import asyncio
import io
import os
import socket
import sys
import threading
from pathlib import Path

import AppKit
import Foundation
import uvicorn
import webview
from PyObjCTools import AppHelper

from app import broadcast, credentials, state
from app.dock_icon_render import blink_alpha, pad_to_square, render_icon, render_spec
from app.main import app

HOST = "127.0.0.1"

WIDGET_WIDTH = 180
WIDGET_HEIGHT = 180
WIDGET_MARGIN = 24

SETTINGS_WIDTH = 420
SETTINGS_HEIGHT = 320

DOCK_ICON_UPDATE_INTERVAL_SECONDS = 45
# Matches static/index.html's/widget.html's RETRY_INTERVAL_MS: poll fast until
# the first successful reading lands, instead of waiting a full interval.
DOCK_ICON_RETRY_INTERVAL_SECONDS = 2
# Matches static/index.html's/widget.html's lcd-blink @keyframes half-cycle
# (1s animation, two phases): ticking the icon this often is what makes it
# visibly blink while stale. Data updates are push-driven (see
# _dock_icon_subscriber_loop below), but blinking is a fixed-cadence local
# animation independent of when new data arrives, so it stays timer-driven.
DOCK_ICON_BLINK_INTERVAL_SECONDS = 0.5

_dock_icon_blink_on = True
_dock_icon_blink_loop_active = False

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


def _render_dock_icon() -> None:
    """Render the Dock icon from current state. Must run on the Cocoa main thread."""
    global _dock_icon_blink_on, _dock_icon_blink_loop_active

    reading = state.get_latest()
    target_low, target_high = state.get_target_range()
    spec = render_spec(
        reading.value if reading is not None else None,
        target_low,
        target_high,
        state.get_error(),
    )

    is_stale = state.get_is_stale()
    _dock_icon_blink_on = (not _dock_icon_blink_on) if is_stale else True
    alpha = blink_alpha(is_stale, _dock_icon_blink_on)
    pil_image = pad_to_square(render_icon(spec, DOCK_ICON_BASE_IMAGE_PATH, DOCK_ICON_FONT_PATH, alpha=alpha))

    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    ns_data = Foundation.NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
    ns_image = AppKit.NSImage.alloc().initWithData_(ns_data)
    AppKit.NSApplication.sharedApplication().setApplicationIconImage_(ns_image)

    if is_stale and not _dock_icon_blink_loop_active:
        _dock_icon_blink_loop_active = True
        AppHelper.callLater(DOCK_ICON_BLINK_INTERVAL_SECONDS, _dock_icon_blink_tick)


def _dock_icon_blink_tick() -> None:
    """Keep re-rendering at the toggled alpha while stale; self-terminates once fresh."""
    global _dock_icon_blink_loop_active
    if not state.get_is_stale():
        _dock_icon_blink_loop_active = False
        return
    _render_dock_icon()
    AppHelper.callLater(DOCK_ICON_BLINK_INTERVAL_SECONDS, _dock_icon_blink_tick)


async def _dock_icon_subscriber_loop() -> None:
    """Runs on the server's event loop; marshals each broadcast onto the Cocoa main thread."""
    queue = broadcast.subscribe()
    AppHelper.callAfter(_render_dock_icon)
    while True:
        await queue.get()
        AppHelper.callAfter(_render_dock_icon)


def _run_server(sock: socket.socket, loop_ready: threading.Event, loop_box: list) -> None:
    async def main() -> None:
        loop_box.append(asyncio.get_running_loop())
        loop_ready.set()
        config = uvicorn.Config(app, host=HOST, log_level="warning")
        await uvicorn.Server(config).serve(sockets=[sock])

    asyncio.run(main())


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


class SettingsApi:
    """Exposed to the settings page as `window.pywebview.api`."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self.settings_window: webview.Window | None = None

    def open(self) -> None:
        """Open the settings window, or bring it to the front if already open."""
        if self.settings_window is not None:
            self.settings_window.show()
            return
        self.settings_window = webview.create_window(
            "Settings",
            f"{self._base_url}/static/settings.html",
            width=SETTINGS_WIDTH,
            height=SETTINGS_HEIGHT,
            resizable=False,
            js_api=self,
        )
        self.settings_window.events.closed += self._on_settings_closed

    def _on_settings_closed(self) -> None:
        self.settings_window = None

    def get_credentials(self) -> dict:
        return {
            "email": os.environ.get("LIBRE_EMAIL", ""),
            "has_password": bool(os.environ.get("LIBRE_PASSWORD")),
        }

    def save_credentials(self, email: str, password: str) -> dict:
        credentials.save(email, password or None)
        return {"ok": True}

    def get_connection_status(self) -> dict:
        return credentials.connection_status()


def _patch_webkit_navigation_action_for_old_webkit() -> None:
    """Work around a pywebview 6.2.1 crash on macOS 10.13's WebKit.

    pywebview's Cocoa navigation delegate unconditionally calls
    ``WKNavigationAction.shouldPerformDownload()``, a property Apple only added in
    macOS 11.3. On 10.13 the selector doesn't exist at all, so the call raises
    inside the delegate callback before it reaches the completion handler -
    WebKit is left waiting forever for a navigation decision (observed as
    WebCore's "Returning empty document" and a leaked completion handler in
    Console.app), so the window stays blank. There's no pywebview release newer
    than 6.2.1 with a fix, and the last version before this call was added
    (5.3.2) is over a year of other fixes behind.

    Patching pywebview's delegate method directly (to guard the call) was tried
    first and crashed with "cannot call block without a signature": its
    `handler` parameter is an Objective-C block, and PyObjC needs bridging
    metadata for that block that's only wired up when the class is defined, not
    when a method is reassigned afterwards. Adding the missing selector onto
    WKNavigationAction itself avoids that entirely - it takes no block argument,
    and pywebview's original, untouched code just works once the selector exists.
    """
    import objc
    import WebKit

    if hasattr(WebKit.WKNavigationAction, "shouldPerformDownload"):
        return

    def shouldPerformDownload(self) -> bool:
        return False

    objc.classAddMethods(
        WebKit.WKNavigationAction,
        [objc.selector(shouldPerformDownload, selector=b"shouldPerformDownload", signature=b"B@:")],
    )


if __name__ == "__main__":
    _patch_webkit_navigation_action_for_old_webkit()

    # Bind to a random free port instead of a fixed one, so the app doesn't
    # clash with anything else already listening on a well-known port.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, 0))
    port = sock.getsockname()[1]
    sock.listen()

    server_loop_ready = threading.Event()
    server_loop_box: list = []
    threading.Thread(
        target=_run_server, args=(sock, server_loop_ready, server_loop_box), daemon=True
    ).start()
    server_loop_ready.wait()
    asyncio.run_coroutine_threadsafe(_dock_icon_subscriber_loop(), server_loop_box[0])

    base_url = f"http://{HOST}:{port}"
    widget_api = WidgetApi(base_url)
    webview.create_window(
        "Freestyle Limón",
        base_url,
        width=480,
        height=500,
        min_size=(360, 480),
        js_api=widget_api,
    )

    settings_api = SettingsApi(base_url)
    settings_menu = webview.Menu('__app__', [webview.menu.MenuAction('Settings…', settings_api.open)])
    webview.start(gui="cocoa", menu=[settings_menu])
