from __future__ import annotations

import argparse
import json
import mimetypes
import re
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .config import AppPaths
from .library import PROJECT_ID, scan_project
from .media import MediaToolError, cache_key, render_context_frame, render_review_clip, require_media_tools
from .store import Store


ALLOWED_HOSTS = {"localhost", "127.0.0.1", "[::1]"}
MAX_JSON_BYTES = 32_768


def parse_byte_range(value: str | None, size: int) -> tuple[int, int] | None:
    if not value or not value.startswith("bytes=") or "," in value:
        return None
    start_raw, separator, end_raw = value[6:].partition("-")
    if not separator:
        return None
    try:
        if not start_raw:
            length = int(end_raw)
            if length <= 0:
                return None
            return max(0, size - length), size - 1
        start = int(start_raw)
        end = int(end_raw) if end_raw else size - 1
    except ValueError:
        return None
    if start < 0 or start >= size or end < start:
        return None
    return start, min(end, size - 1)


def _date_label(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%B %-d, %Y")
    except (ValueError, TypeError):
        return value


@dataclass
class Application:
    paths: AppPaths
    store: Store
    default_source: str = ""

    def state(self) -> dict[str, Any]:
        projects = self.store.projects()
        if not projects:
            return {"project": None, "summary": None, "candidate": None, "default_source": self.default_source}
        project = projects[0]
        return {
            "project": project,
            "summary": self.store.summary(project["id"]),
            "candidate": self.candidate_payload(self.store.next_candidate(project["id"])),
            "default_source": self.default_source,
        }

    def candidate_payload(self, candidate: dict[str, Any] | None) -> dict[str, Any] | None:
        if not candidate:
            return None
        candidate_id = candidate["id"]
        return {
            **candidate,
            "captured_label": _date_label(candidate["captured_at"]),
            "title": f"A sustained view from {candidate['chapter'].lower()}",
            "video_url": f"/media/candidates/{candidate_id}.mp4",
            "context_urls": [
                f"/media/candidates/{candidate_id}/context/1.jpg",
                f"/media/candidates/{candidate_id}/context/2.jpg",
            ],
        }

    def candidate_asset(self, candidate_id: int, kind: str, context_index: int = 0) -> Path:
        candidate = self.store.candidate(candidate_id)
        if not candidate:
            raise KeyError(candidate_id)
        source = Path(candidate["path"]).resolve(strict=True)
        project = self.store.project(candidate["project_id"])
        if not project:
            raise KeyError(candidate["project_id"])
        source_root = Path(project["source_dir"]).resolve(strict=True)
        if source.parent != source_root:
            raise PermissionError("Candidate source is outside the project root.")
        start = float(candidate["start_seconds"])
        duration = float(candidate["duration"])
        asset_dir = self.paths.cache / candidate["project_id"] / "review"
        if kind == "video":
            key = cache_key(source, start, duration, "review-360p-v1")
            return render_review_clip(source, asset_dir / f"{key}.mp4", start, duration)
        if context_index not in {1, 2}:
            raise ValueError("invalid context frame")
        offset = 0.25 if context_index == 1 else 0.75
        timestamp = min(float(candidate["source_duration"]) - 0.05, start + duration * offset)
        key = cache_key(source, timestamp, 0.0, f"context-{context_index}-360p-v1")
        return render_context_frame(source, asset_dir / f"{key}.jpg", timestamp)


def handler_factory(application: Application) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "PyreneesSelects/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            print(f"[{self.log_date_time_string()}] {format % args}")

        def _host_allowed(self) -> bool:
            host = self.headers.get("Host", "").split(":", 1)[0].lower()
            if host in ALLOWED_HOSTS:
                return True
            self._json({"error": "This local application only accepts localhost requests."}, HTTPStatus.FORBIDDEN)
            return False

        def _headers(self, status: HTTPStatus, content_type: str, length: int | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; media-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
            )
            if length is not None:
                self.send_header("Content-Length", str(length))
            self.end_headers()

        def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(body))
            self.wfile.write(body)

        def _read_json(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("Invalid request length.") from exc
            if length <= 0 or length > MAX_JSON_BYTES:
                raise ValueError("Request body is empty or too large.")
            try:
                payload = json.loads(self.rfile.read(length))
            except json.JSONDecodeError as exc:
                raise ValueError("Request body must be valid JSON.") from exc
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            return payload

        def _serve_file(self, path: Path, content_type: str | None = None, allow_ranges: bool = False) -> None:
            if not path.is_file():
                self._json({"error": "File not found."}, HTTPStatus.NOT_FOUND)
                return
            size = path.stat().st_size
            byte_range = parse_byte_range(self.headers.get("Range"), size) if allow_ranges else None
            if byte_range:
                start, end = byte_range
                length = end - start + 1
                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header("Content-Type", content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(length))
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "private, max-age=86400")
                self.end_headers()
                with path.open("rb") as handle:
                    handle.seek(start)
                    remaining = length
                    while remaining:
                        chunk = handle.read(min(64 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(size))
            if allow_ranges:
                self.send_header("Accept-Ranges", "bytes")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "private, max-age=86400" if allow_ranges else "no-store")
            self.end_headers()
            with path.open("rb") as handle:
                while chunk := handle.read(64 * 1024):
                    self.wfile.write(chunk)

        def do_GET(self) -> None:
            if not self._host_allowed():
                return
            path = unquote(urlparse(self.path).path)
            try:
                if path == "/api/state":
                    self._json(application.state())
                    return
                match = re.fullmatch(r"/media/candidates/(\d+)\.mp4", path)
                if match:
                    asset = application.candidate_asset(int(match.group(1)), "video")
                    self._serve_file(asset, "video/mp4", allow_ranges=True)
                    return
                match = re.fullmatch(r"/media/candidates/(\d+)/context/([12])\.jpg", path)
                if match:
                    asset = application.candidate_asset(int(match.group(1)), "context", int(match.group(2)))
                    self._serve_file(asset, "image/jpeg")
                    return
                static_name = "index.html" if path in {"/", "/index.html"} else path.removeprefix("/")
                if static_name not in {"index.html", "styles.css", "app.js"}:
                    self._json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
                    return
                self._serve_file(application.paths.static / static_name)
            except (KeyError, FileNotFoundError):
                self._json({"error": "Candidate or source media was not found."}, HTTPStatus.NOT_FOUND)
            except (MediaToolError, PermissionError, ValueError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.UNPROCESSABLE_ENTITY)

        def do_POST(self) -> None:
            if not self._host_allowed():
                return
            path = unquote(urlparse(self.path).path)
            try:
                payload = self._read_json()
                if path == "/api/projects":
                    name = str(payload.get("name") or "Pyrenees 2024").strip()[:80]
                    source = Path(str(payload.get("source_dir") or "")).expanduser().resolve(strict=True)
                    if not source.is_dir():
                        raise ValueError("Choose an existing footage folder.")
                    project = application.store.upsert_project(PROJECT_ID, name, str(source))
                    self._json({"project": project}, HTTPStatus.CREATED)
                    return
                if path == "/api/scan":
                    project_id = str(payload.get("project_id") or PROJECT_ID)
                    self._json(scan_project(application.store, project_id))
                    return
                match = re.fullmatch(r"/api/candidates/(\d+)/decision", path)
                if match:
                    candidate = application.store.decide(
                        int(match.group(1)), str(payload.get("decision") or ""), payload.get("story_role") or None
                    )
                    project_id = candidate["project_id"]
                    self._json({
                        "candidate": application.candidate_payload(candidate),
                        "next_candidate": application.candidate_payload(application.store.next_candidate(project_id)),
                        "summary": application.store.summary(project_id),
                    })
                    return
                self._json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            except FileNotFoundError:
                self._json({"error": "That folder does not exist."}, HTTPStatus.BAD_REQUEST)
            except NotADirectoryError:
                self._json({"error": "Choose a folder, not a file."}, HTTPStatus.BAD_REQUEST)
            except KeyError:
                self._json({"error": "Project or candidate not found."}, HTTPStatus.NOT_FOUND)
            except (ValueError, MediaToolError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.UNPROCESSABLE_ENTITY)

    return Handler


def build_application(data_dir: Path | None = None, default_source: str = "") -> Application:
    paths = AppPaths.build(data_dir)
    paths.ensure()
    require_media_tools()
    return Application(paths=paths, store=Store(paths.database), default_source=default_source)


def run(host: str, port: int, data_dir: Path | None = None, default_source: str = "", open_browser: bool = True) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Pyrenees Selects only binds to the local machine.")
    application = build_application(data_dir=data_dir, default_source=default_source)
    server = ThreadingHTTPServer((host, port), handler_factory(application))
    url = f"http://localhost:{port}"
    print(f"Pyrenees Selects is running at {url}")
    print(f"Local data: {application.paths.root}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Pyrenees Selects.")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Pyrenees Selects application.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8741, type=int)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--source", default="", help="Suggested footage folder on the create-project screen.")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    run(args.host, args.port, args.data_dir, args.source, not args.no_browser)


if __name__ == "__main__":
    main()
