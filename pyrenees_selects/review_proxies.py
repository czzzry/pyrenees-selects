from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable

from .media import render_source_proxy
from .preeditor import PreEditor


ProxyRenderer = Callable[[Path, Path], Path]


class ReviewProxyManager:
    """Resumable, project-scoped preparation of disposable review copies.

    Completion is represented by cache files rather than database state. A
    restarted app can therefore resume by skipping files already prepared.
    """

    def __init__(self, editor: PreEditor, cache: Path, *, renderer: ProxyRenderer = render_source_proxy):
        self.editor = editor
        self.cache = cache.expanduser().resolve() / "preeditor" / "review-proxies"
        self.renderer = renderer
        self._lock = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}
        self._running_source: dict[str, str] = {}
        self._errors: dict[str, dict[str, str]] = {}

    def _destination(self, source: dict[str, Any]) -> Path:
        identity = str(source.get("fingerprint") or "unknown")[:12]
        return self.cache / f"{source['id']}-{identity}.mp4"

    def proxy_path(self, source_id: str) -> Path | None:
        source = self.editor.source(source_id)
        if not source:
            return None
        destination = self._destination(source)
        return destination if destination.is_file() and destination.stat().st_size > 0 else None

    def status(self, project_id: str) -> dict[str, Any]:
        if not self.editor.project(project_id):
            raise KeyError(project_id)
        sources = [source for source in self.editor.sources(project_id) if source["status"] == "ready"]
        ready_ids = [str(source["id"]) for source in sources if self.proxy_path(str(source["id"]))]
        with self._lock:
            thread = self._threads.get(project_id)
            active = bool(thread and thread.is_alive())
            running_source_id = self._running_source.get(project_id)
            errors = dict(self._errors.get(project_id) or {})
        pending = max(0, len(sources) - len(ready_ids) - len(errors))
        state = "running" if active else "ready" if sources and len(ready_ids) == len(sources) else "attention" if errors else "idle"
        running = next((source for source in sources if source["id"] == running_source_id), None)
        total_seconds = sum(float(source.get("duration") or 0) for source in sources)
        return {
            "state": state,
            "total": len(sources),
            "ready": len(ready_ids),
            "pending": pending,
            "failed": len(errors),
            "ready_source_ids": ready_ids,
            "running_source_id": running_source_id,
            "running_filename": str(running.get("filename") or "") if running else "",
            "estimated_bytes": int(total_seconds * 190_000),
            "errors": errors,
        }

    def start(self, project_id: str) -> dict[str, Any]:
        if not self.editor.project(project_id):
            raise KeyError(project_id)
        with self._lock:
            existing = self._threads.get(project_id)
            if not (existing and existing.is_alive()):
                self._errors[project_id] = {}
                thread = threading.Thread(target=self._run, args=(project_id,), daemon=True, name=f"review-proxies-{project_id}")
                self._threads[project_id] = thread
                thread.start()
        return self.status(project_id)

    def _run(self, project_id: str) -> None:
        sources = [source for source in self.editor.sources(project_id) if source["status"] == "ready"]
        for source in sources:
            destination = self._destination(source)
            if destination.is_file() and destination.stat().st_size > 0:
                continue
            with self._lock:
                self._running_source[project_id] = str(source["id"])
            try:
                self.renderer(Path(str(source["current_path"])), destination)
            except Exception as exc:
                with self._lock:
                    self._errors.setdefault(project_id, {})[str(source["id"])] = str(exc)[:500]
        with self._lock:
            self._running_source.pop(project_id, None)
