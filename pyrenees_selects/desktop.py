from __future__ import annotations

import base64
import fcntl
import json
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

from .analysis import ANALYSIS_VERSION, analyze_video
from .config import AppPaths
from .server import Application, build_application


APP_TITLE = "Pyrenees Selects"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PreparationJob:
    def __init__(self, application: Application) -> None:
        self.application = application
        self.status_path = application.paths.root / "preparation-status.json"
        self.lock = threading.Lock()
        self.cancel_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.caffeinate: subprocess.Popen[bytes] | None = None
        self._status = self._read_status()
        if self._status.get("state") == "running":
            self._status.update(state="interrupted", message="Preparation was interrupted. Resume to continue from saved work.")
            self._write_status()

    def _read_status(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.status_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {"state": "idle", "message": "Ready for overnight preparation."}

    def _write_status(self) -> None:
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.status_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._status, indent=2), encoding="utf-8")
        temporary.replace(self.status_path)

    def _update(self, **changes: Any) -> None:
        with self.lock:
            self._status.update(changes, updated_at=_now())
            self._write_status()

    def status(self, project_id: str) -> dict[str, Any]:
        with self.lock:
            status = dict(self._status)
        if status.get("project_id") != project_id and status.get("state") == "running":
            return {
                "state": "blocked",
                "project_id": project_id,
                "message": "Another project is currently preparing. Let it finish or pause it before starting this library.",
            }
        if status.get("project_id") != project_id:
            return {"state": "idle", "project_id": project_id, "message": "Ready for overnight preparation."}
        return status

    def start(self, project_id: str) -> dict[str, Any]:
        if self.thread and self.thread.is_alive():
            return self.status(project_id)
        project = self.application.store.project(project_id)
        if not project:
            raise KeyError(project_id)
        candidates = self.application.store.project_candidates(project_id)
        if not candidates:
            raise ValueError("Scan the footage library before starting preparation.")
        free_bytes = shutil.disk_usage(self.application.paths.root).free
        if free_bytes < 2 * 1024**3:
            raise ValueError("At least 2 GB of free disk space is required for disposable review media.")
        self.cancel_event.clear()
        self._status = {
            "state": "running",
            "stage": "analysis",
            "project_id": project_id,
            "processed": 0,
            "total": len(candidates) * 2,
            "analyzed": 0,
            "prepared": 0,
            "failures": [],
            "current_file": "",
            "started_at": _now(),
            "updated_at": _now(),
            "message": "Analyzing sparse low-resolution samples. Originals remain untouched.",
            "free_bytes_at_start": free_bytes,
        }
        self._write_status()
        self.caffeinate = subprocess.Popen(["/usr/bin/caffeinate", "-dimsu"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.thread = threading.Thread(target=self._run, args=(project_id,), name="pyrenees-preparation", daemon=True)
        self.thread.start()
        return self.status(project_id)

    def cancel(self) -> dict[str, Any]:
        self.cancel_event.set()
        return dict(self._status)

    def _run(self, project_id: str) -> None:
        failures: list[dict[str, str]] = []
        try:
            candidates = self.application.store.project_candidates(project_id)
            analyzed = 0
            for candidate in candidates:
                if self.cancel_event.is_set():
                    raise InterruptedError("Preparation paused.")
                self._update(current_file=candidate["filename"], stage="analysis")
                if int(candidate.get("analysis_version") or 0) < ANALYSIS_VERSION and candidate["decision"] == "pending":
                    result = analyze_video(Path(candidate["path"]), float(candidate["source_duration"]), self.cancel_event)
                    self.application.store.update_candidate_analysis(
                        int(candidate["id"]), result.start_seconds, result.duration, result.reason, result.score, ANALYSIS_VERSION
                    )
                analyzed += 1
                self._update(processed=analyzed, analyzed=analyzed)

            candidates = self.application.store.project_candidates(project_id)
            prepared = 0
            self._update(stage="proxies", message="Preparing 360p review clips and context frames.")
            for candidate in candidates:
                if self.cancel_event.is_set():
                    raise InterruptedError("Preparation paused.")
                self._update(current_file=candidate["filename"])
                try:
                    self.application.candidate_asset(int(candidate["id"]), "video")
                    self.application.candidate_asset(int(candidate["id"]), "context", 1)
                    self.application.candidate_asset(int(candidate["id"]), "context", 2)
                except Exception as exc:
                    failures.append({"filename": candidate["filename"], "error": str(exc)})
                prepared += 1
                self._update(processed=len(candidates) + prepared, prepared=prepared, failures=failures)
            message = "Morning-ready: ranked candidates and review media are prepared."
            if failures:
                message += f" {len(failures)} item(s) need another attempt."
            self._update(state="complete", stage="complete", current_file="", message=message, finished_at=_now())
        except InterruptedError:
            self._update(state="interrupted", message="Preparation paused safely. Resume to continue from saved analysis.")
        except Exception as exc:
            self._update(state="failed", message=str(exc), finished_at=_now())
        finally:
            if self.caffeinate and self.caffeinate.poll() is None:
                self.caffeinate.terminate()
                try:
                    self.caffeinate.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.caffeinate.kill()
            self.caffeinate = None


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
        self.preparation = PreparationJob(application)
        self.window: Any = None

    def state(self) -> dict[str, Any]:
        return self.application.state()

    def create_project(self, name: str, source_dir: str) -> dict[str, Any]:
        return {"project": self.application.create_project(name, source_dir)}

    def open_project(self, project_id: str) -> dict[str, Any]:
        return self.application.open_project(project_id)

    def scan(self, project_id: str) -> dict[str, Any]:
        return self.application.scan(project_id)

    def decide(self, candidate_id: int, decision: str, story_role: str | None = None) -> dict[str, Any]:
        return self.application.decide(candidate_id, decision, story_role)

    def preparation_status(self, project_id: str) -> dict[str, Any]:
        return self.preparation.status(project_id)

    def start_preparation(self, project_id: str) -> dict[str, Any]:
        return self.preparation.start(project_id)

    def cancel_preparation(self) -> dict[str, Any]:
        return self.preparation.cancel()

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
