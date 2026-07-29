"""Entry point for the standalone executable (see `pyinstaller` build in README)."""
import threading
import webbrowser

import uvicorn

from app.main import app

if __name__ == "__main__":
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8000")).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)
