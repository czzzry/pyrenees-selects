from __future__ import annotations

import fcntl
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import IO, Any

from .config import AppPaths
from .preeditor_server import Handler, SelectsApplication


APP_TITLE = "Selects"


class SingleInstance:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self.handle: IO[str] | None = None

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.lock_path.open("w")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.close()
            self.handle = None
            return False
        return True

    def release(self) -> None:
        if self.handle:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None


class DesktopBridge:
    def __init__(self) -> None:
        self.window: Any = None

    def choose_folder(self, current: str = "") -> str:
        import webview

        initial = Path(current).expanduser() if current else Path.home()
        if not initial.is_dir():
            initial = initial.parent if initial.parent.is_dir() else Path.home()
        selected = self.window.create_file_dialog(webview.FileDialog.FOLDER, directory=str(initial))
        return selected[0] if selected else ""

    def choose_file(self, current: str = "") -> str:
        import webview

        initial = Path(current).expanduser() if current else Path.home()
        directory = initial if initial.is_dir() else initial.parent
        if not directory.is_dir():
            directory = Path.home()
        selected = self.window.create_file_dialog(webview.FileDialog.OPEN, directory=str(directory))
        return selected[0] if selected else ""


def main() -> None:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("The Selects desktop runtime is missing. Reinstall Selects.app.") from exc

    paths = AppPaths.build_selects()
    paths.ensure()
    instance = SingleInstance(paths.root / ".desktop.lock")
    if not instance.acquire():
        return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.application = SelectsApplication(paths)  # type: ignore[attr-defined]
    server_thread = threading.Thread(target=server.serve_forever, name="selects-local-server", daemon=True)
    server_thread.start()
    bridge = DesktopBridge()
    try:
        window = webview.create_window(
            APP_TITLE,
            f"http://127.0.0.1:{server.server_port}/",
            js_api=bridge,
            width=1480,
            height=940,
            min_size=(980, 680),
            background_color="#f5f5f2",
            text_select=True,
        )
        bridge.window = window
        webview.start(gui="cocoa", private_mode=False, storage_path=str(paths.root / "WebKit"))
    except Exception as exc:
        print(f"{APP_TITLE} could not start: {exc}", file=sys.stderr)
        raise
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=3)
        instance.release()


if __name__ == "__main__":
    main()
