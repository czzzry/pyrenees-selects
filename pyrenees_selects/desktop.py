from __future__ import annotations

import base64
import fcntl
import sys
from pathlib import Path
from typing import IO, Any

from .config import AppPaths
from .server import Application, build_application


APP_TITLE = "Pyrenees Selects"


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


class DesktopApi:
    def __init__(self, application: Application) -> None:
        self.application = application
        self.window: Any = None

    def state(self) -> dict[str, Any]:
        return self.application.state()

    def create_project(self, name: str, source_dir: str) -> dict[str, Any]:
        return {"project": self.application.create_project(name, source_dir)}

    def scan(self, project_id: str) -> dict[str, Any]:
        return self.application.scan(project_id)

    def decide(self, candidate_id: int, decision: str, story_role: str | None = None) -> dict[str, Any]:
        return self.application.decide(candidate_id, decision, story_role)

    def candidate_assets(self, candidate_id: int) -> dict[str, Any]:
        video = self.application.candidate_asset(candidate_id, "video")
        context_one = self.application.candidate_asset(candidate_id, "context", 1)
        context_two = self.application.candidate_asset(candidate_id, "context", 2)
        return {
            "video_base64": base64.b64encode(video.read_bytes()).decode("ascii"),
            "context_data_urls": [
                f"data:image/jpeg;base64,{base64.b64encode(context_one.read_bytes()).decode('ascii')}",
                f"data:image/jpeg;base64,{base64.b64encode(context_two.read_bytes()).decode('ascii')}",
            ],
        }

    def choose_footage_folder(self, current: str = "") -> str:
        import webview

        initial = Path(current).expanduser() if current else Path.home()
        if not initial.is_dir():
            initial = initial.parent if initial.parent.is_dir() else Path.home()
        selected = self.window.create_file_dialog(webview.FileDialog.FOLDER, directory=str(initial))
        return selected[0] if selected else ""


def main() -> None:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("The desktop runtime is missing. Rebuild Pyrenees Selects.app.") from exc

    paths = AppPaths.build()
    instance = SingleInstance(paths.root / ".desktop.lock")
    if not instance.acquire():
        return

    try:
        application = build_application()
        api = DesktopApi(application)
        window_url = f"{(application.paths.static / 'index.html').as_uri()}?desktop=1"
        window = webview.create_window(
            APP_TITLE,
            window_url,
            js_api=api,
            width=1440,
            height=900,
            min_size=(980, 680),
            background_color="#f4f1e9",
            text_select=True,
        )
        api.window = window
        webview.start(gui="cocoa", private_mode=False, storage_path=str(paths.root / "WebKit"))
    except Exception as exc:
        # In a windowed app there is no terminal. macOS records this in Console,
        # while development launches still get a useful failure message.
        print(f"{APP_TITLE} could not start: {exc}", file=sys.stderr)
        raise
    finally:
        instance.release()


if __name__ == "__main__":
    main()
