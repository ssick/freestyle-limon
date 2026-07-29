"""Entry point for the standalone macOS app (see `pyinstaller` build in README)."""
import socket
import threading

import uvicorn
import webview

from app.main import app

HOST = "127.0.0.1"


def _run_server(sock: socket.socket) -> None:
    config = uvicorn.Config(app, host=HOST, log_level="warning")
    uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    # Bind to a random free port instead of a fixed one, so the app doesn't
    # clash with anything else already listening on a well-known port.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, 0))
    port = sock.getsockname()[1]
    sock.listen()

    threading.Thread(target=_run_server, args=(sock,), daemon=True).start()
    webview.create_window(
        "Freestyle Limón",
        f"http://{HOST}:{port}",
        width=480,
        height=800,
        min_size=(360, 600),
    )
    webview.start(gui="cocoa")
