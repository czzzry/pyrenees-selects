from __future__ import annotations

import argparse
import json
import mimetypes
import re
import threading
import uuid
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
from .treatment_plan import LONG_ROUGH_CUT_ADDITIONS, LONG_ROUGH_CUT_ORDER


ALLOWED_HOSTS = {"localhost", "127.0.0.1", "[::1]"}
MAX_JSON_BYTES = 32_768
STORY_GROUP_TITLES = {
    "ocean": "Ocean opening",
    "early-mountains": "First mountain air",
    "human-journey": "A human thread",
    "paths": "Into the trail",
    "clouds": "Above the clouds",
    "water": "Water in the valley",
    "high-mountains": "The high country",
    "ending": "Cloud-sea ending",
    "bird": "The bird encounter",
}
HYBRID_REVIEW_RECIPES = {recipe.candidate_id: recipe for recipe in LONG_ROUGH_CUT_ADDITIONS}
HYBRID_REVIEW_ORDER = tuple(
    candidate_id for candidate_id in LONG_ROUGH_CUT_ORDER if candidate_id in HYBRID_REVIEW_RECIPES
)


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

    def state(self, project_id: str | None = None) -> dict[str, Any]:
        projects = self.store.projects()
        if not projects:
            return {
                "project": None,
                "projects": [],
                "summary": None,
                "candidate": None,
                "refinement_summary": None,
                "storyboard_summary": None,
                "hybrid_summary": None,
                "default_source": self.default_source,
            }
        selected_id = project_id or self.store.setting("active_project_id")
        project = self.store.project(selected_id) if selected_id else None
        if not project:
            project = projects[0]
        self.store.set_setting("active_project_id", project["id"])
        return {
            "project": project,
            "projects": projects,
            "summary": self.store.summary(project["id"]),
            "candidate": self.candidate_payload(self.store.next_candidate(project["id"])),
            "refinement_summary": self.store.refinement_summary(project["id"]),
            "storyboard_summary": self.store.storyboard_summary(project["id"]),
            "hybrid_summary": self.store.hybrid_review_summary(project["id"], HYBRID_REVIEW_ORDER),
            "default_source": self.default_source,
        }

    def create_project(self, name: str, source_dir: str) -> dict[str, Any]:
        safe_name = (name or "Pyrenees 2024").strip()[:80]
        source = Path(source_dir).expanduser().resolve(strict=True)
        if not source.is_dir():
            raise ValueError("Choose an existing footage folder.")
        existing = next((project for project in self.store.projects() if project["source_dir"] == str(source)), None)
        project_id = existing["id"] if existing else f"project-{uuid.uuid4().hex[:12]}"
        project = self.store.upsert_project(project_id, safe_name, str(source))
        self.store.set_setting("active_project_id", project_id)
        return project

    def open_project(self, project_id: str) -> dict[str, Any]:
        if not self.store.project(project_id):
            raise KeyError(project_id)
        self.store.set_setting("active_project_id", project_id)
        return self.state(project_id)

    def scan(self, project_id: str = "") -> dict[str, Any]:
        selected = project_id or self.store.setting("active_project_id") or PROJECT_ID
        return scan_project(self.store, selected)

    def decide(self, candidate_id: int, decision: str, story_role: str | None = None) -> dict[str, Any]:
        candidate = self.store.decide(candidate_id, decision, story_role)
        project_id = candidate["project_id"]
        return {
            "candidate": self.candidate_payload(candidate),
            "next_candidate": self.candidate_payload(self.store.next_candidate(project_id)),
            "summary": self.store.summary(project_id),
            "refinement_summary": self.store.refinement_summary(project_id),
        }

    def candidate_payload(self, candidate: dict[str, Any] | None) -> dict[str, Any] | None:
        if not candidate:
            return None
        candidate_id = candidate["id"]
        return {
            **candidate,
            "note": candidate.get("note") or "",
            "captured_label": _date_label(candidate["captured_at"]),
            "title": f"A sustained view from {candidate['chapter'].lower()}",
            "video_url": f"/media/candidates/{candidate_id}.mp4",
            "source_video_url": f"/media/candidates/{candidate_id}/source",
            "context_urls": [
                f"/media/candidates/{candidate_id}/context/1.jpg",
                f"/media/candidates/{candidate_id}/context/2.jpg",
            ],
        }

    def save_candidate_note(self, candidate_id: int, note: str) -> dict[str, Any]:
        candidate = self.store.save_candidate_note(candidate_id, note)
        return {"candidate": self.candidate_payload(candidate)}

    def refinement_payload(self, candidate: dict[str, Any]) -> dict[str, Any]:
        start = float(candidate["start_seconds"])
        duration = float(candidate["duration"])
        return {
            **candidate,
            "note": candidate.get("note") or "",
            "captured_label": _date_label(candidate["captured_at"]),
            "title": f"A sustained view from {candidate['chapter'].lower()}",
            "preview_start_seconds": start,
            "preview_duration": duration,
            "refinement_video_url": f"/media/candidates/{candidate['id']}.mp4",
        }

    def refinement_state(self, project_id: str | None = None) -> dict[str, Any]:
        selected = project_id or self.store.setting("active_project_id")
        if not selected or not self.store.project(selected):
            raise KeyError(selected or "")
        return {
            "candidates": [self.refinement_payload(candidate) for candidate in self.store.refinement_candidates(selected)],
            "summary": self.store.refinement_summary(selected),
        }

    def save_refinement(
        self,
        candidate_id: int,
        note: str,
        note_anchor_seconds: float | None = None,
        reviewed: bool = False,
    ) -> dict[str, Any]:
        candidate = self.store.save_refinement(candidate_id, note, note_anchor_seconds, reviewed)
        return {
            "candidate": self.refinement_payload(candidate),
            "summary": self.store.refinement_summary(candidate["project_id"]),
        }

    def storyboard_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            **item,
            "captured_label": _date_label(item["captured_at"]),
            "title": STORY_GROUP_TITLES.get(item["story_group"], item["story_group"].replace("-", " ").title()),
            "storyboard_video_url": f"/media/storyboard/{item['candidate_id']}.mp4",
        }

    def storyboard_state(self, project_id: str | None = None, variant_seconds: int = 120) -> dict[str, Any]:
        selected = project_id or self.store.setting("active_project_id")
        if not selected or not self.store.project(selected):
            raise KeyError(selected or "")
        return {
            "variant_seconds": variant_seconds,
            "items": [self.storyboard_payload(item) for item in self.store.storyboard_items(selected, variant_seconds)],
            "alternatives": [self.storyboard_payload(item) for item in self.store.storyboard_alternatives(selected, variant_seconds)],
            "summary": self.store.storyboard_summary(selected),
            "bird": self.store.edit_plan_item(78),
        }

    def review_storyboard_item(
        self,
        storyboard_item_id: int,
        decision: str,
        replacement_candidate_id: int | None = None,
    ) -> dict[str, Any]:
        self.store.review_storyboard_item(storyboard_item_id, decision, replacement_candidate_id)
        return self.storyboard_state(variant_seconds=120)

    def save_storyboard_note(self, storyboard_item_id: int, note: str) -> dict[str, Any]:
        return self.store.save_storyboard_note(storyboard_item_id, note)

    def hybrid_state(self, project_id: str | None = None) -> dict[str, Any]:
        selected = project_id or self.store.setting("active_project_id")
        if not selected or not self.store.project(selected):
            raise KeyError(selected or "")
        items = self.store.hybrid_review_items(selected, HYBRID_REVIEW_ORDER)
        if len(items) != len(HYBRID_REVIEW_ORDER):
            raise ValueError("The longer-cut selection review is not available for this project.")
        payloads = []
        for item in items:
            recipe = HYBRID_REVIEW_RECIPES[int(item["candidate_id"])]
            payloads.append({
                **self.storyboard_payload(item),
                "hybrid_video_url": f"/media/hybrid/{item['candidate_id']}.mp4",
                "hybrid_source_start_seconds": recipe.source_start,
                "hybrid_source_duration": recipe.source_duration,
                "hybrid_output_duration": recipe.output_duration,
                "hybrid_rationale": recipe.rationale,
            })
        return {
            "items": payloads,
            "summary": self.store.hybrid_review_summary(selected, HYBRID_REVIEW_ORDER),
        }

    def review_hybrid_item(self, storyboard_item_id: int, decision: str) -> dict[str, Any]:
        current = self.hybrid_state()
        allowed = {int(item["storyboard_item_id"]) for item in current["items"]}
        if storyboard_item_id not in allowed:
            raise KeyError(storyboard_item_id)
        saved = self.store.save_hybrid_review(storyboard_item_id, decision)
        return self.hybrid_state(str(saved["project_id"]))

    def hybrid_asset(self, candidate_id: int) -> Path:
        if candidate_id not in HYBRID_REVIEW_RECIPES:
            raise KeyError(candidate_id)
        try:
            status = json.loads((self.paths.root / "treated-long-rough-cut-status.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FileNotFoundError("The completed longer-cut treatments are not available.") from exc
        render_id = str(status.get("render_id") or "")
        if status.get("state") != "complete" or not re.fullmatch(r"[a-f0-9]{12}", render_id):
            raise FileNotFoundError("The completed longer-cut treatments are not available.")
        directory = (self.paths.cache / PROJECT_ID / "treated-long" / render_id).resolve(strict=True)
        matches = list(directory.glob(f"*-{candidate_id:03d}-*.mp4"))
        if len(matches) != 1:
            raise FileNotFoundError(f"The treated review clip for candidate {candidate_id} is missing.")
        asset = matches[0].resolve(strict=True)
        if asset.parent != directory:
            raise PermissionError("The treated review clip is outside the expected cache.")
        return asset

    def storyboard_asset(self, candidate_id: int) -> Path:
        plan = self.store.edit_plan_item(candidate_id)
        if not plan:
            raise KeyError(candidate_id)
        source = Path(plan["path"]).resolve(strict=True)
        project = self.store.project(plan["project_id"])
        if not project:
            raise KeyError(plan["project_id"])
        if source.parent != Path(project["source_dir"]).resolve(strict=True):
            raise PermissionError("Candidate source is outside the project root.")
        start = float(plan["proposed_start_seconds"])
        duration = float(plan["proposed_duration"])
        if (
            abs(start - float(plan["original_start_seconds"])) < 0.001
            and abs(duration - float(plan["original_duration"])) < 0.001
        ):
            return self.candidate_asset(candidate_id, "video")
        key = cache_key(source, start, duration, "storyboard-360p-v1")
        destination = self.paths.cache / plan["project_id"] / "storyboard" / f"{key}.mp4"
        return render_review_clip(source, destination, start, duration, timeout_seconds=900)

    def _validated_candidate_source(self, candidate: dict[str, Any]) -> Path:
        source = Path(candidate["path"]).resolve(strict=True)
        project = self.store.project(candidate["project_id"])
        if not project:
            raise KeyError(candidate["project_id"])
        source_root = Path(project["source_dir"]).resolve(strict=True)
        if source.parent != source_root:
            raise PermissionError("Candidate source is outside the project root.")
        return source

    def candidate_source(self, candidate_id: int) -> Path:
        candidate = self.store.candidate(candidate_id)
        if not candidate:
            raise KeyError(candidate_id)
        return self._validated_candidate_source(candidate)

    def candidate_asset(self, candidate_id: int, kind: str, context_index: int = 0) -> Path:
        candidate = self.store.candidate(candidate_id)
        if not candidate:
            raise KeyError(candidate_id)
        source = self._validated_candidate_source(candidate)
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
        server_version = "PyreneesSelects/0.4"

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
                if path == "/api/refinement":
                    self._json(application.refinement_state())
                    return
                if path == "/api/storyboard":
                    query = urlparse(self.path).query
                    variant_match = re.search(r"(?:^|&)variant=(90|120|180)(?:&|$)", query)
                    variant = int(variant_match.group(1)) if variant_match else 120
                    self._json(application.storyboard_state(variant_seconds=variant))
                    return
                if path == "/api/hybrid":
                    self._json(application.hybrid_state())
                    return
                match = re.fullmatch(r"/media/candidates/(\d+)\.mp4", path)
                if match:
                    asset = application.candidate_asset(int(match.group(1)), "video")
                    self._serve_file(asset, "video/mp4", allow_ranges=True)
                    return
                match = re.fullmatch(r"/media/candidates/(\d+)/source", path)
                if match:
                    source = application.candidate_source(int(match.group(1)))
                    self._serve_file(source, allow_ranges=True)
                    return
                match = re.fullmatch(r"/media/storyboard/(\d+)\.mp4", path)
                if match:
                    asset = application.storyboard_asset(int(match.group(1)))
                    self._serve_file(asset, "video/mp4", allow_ranges=True)
                    return
                match = re.fullmatch(r"/media/hybrid/(\d+)\.mp4", path)
                if match:
                    asset = application.hybrid_asset(int(match.group(1)))
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
                    project = application.create_project(
                        str(payload.get("name") or "Pyrenees 2024"),
                        str(payload.get("source_dir") or ""),
                    )
                    self._json({"project": project}, HTTPStatus.CREATED)
                    return
                if path == "/api/projects/open":
                    self._json(application.open_project(str(payload.get("project_id") or "")))
                    return
                if path == "/api/scan":
                    project_id = str(payload.get("project_id") or "")
                    self._json(application.scan(project_id))
                    return
                match = re.fullmatch(r"/api/candidates/(\d+)/decision", path)
                if match:
                    self._json(application.decide(
                        int(match.group(1)),
                        str(payload.get("decision") or ""),
                        payload.get("story_role") or None,
                    ))
                    return
                match = re.fullmatch(r"/api/candidates/(\d+)/note", path)
                if match:
                    self._json(application.save_candidate_note(
                        int(match.group(1)),
                        str(payload.get("note") or ""),
                    ))
                    return
                match = re.fullmatch(r"/api/refinements/(\d+)", path)
                if match:
                    anchor = payload.get("note_anchor_seconds")
                    self._json(application.save_refinement(
                        int(match.group(1)),
                        str(payload.get("note") or ""),
                        float(anchor) if anchor is not None else None,
                        bool(payload.get("reviewed", False)),
                    ))
                    return
                match = re.fullmatch(r"/api/storyboard/items/(\d+)", path)
                if match:
                    replacement = payload.get("replacement_candidate_id")
                    self._json(application.review_storyboard_item(
                        int(match.group(1)),
                        str(payload.get("decision") or ""),
                        int(replacement) if replacement is not None else None,
                    ))
                    return
                match = re.fullmatch(r"/api/hybrid/items/(\d+)", path)
                if match:
                    self._json(application.review_hybrid_item(
                        int(match.group(1)),
                        str(payload.get("decision") or ""),
                    ))
                    return
                match = re.fullmatch(r"/api/storyboard/items/(\d+)/note", path)
                if match:
                    self._json(application.save_storyboard_note(
                        int(match.group(1)),
                        str(payload.get("note") or ""),
                    ))
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


def create_local_server(
    data_dir: Path | None = None,
    default_source: str = "",
    host: str = "127.0.0.1",
    port: int = 0,
) -> tuple[ThreadingHTTPServer, Application]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Pyrenees Selects only binds to the local machine.")
    application = build_application(data_dir=data_dir, default_source=default_source)
    server = ThreadingHTTPServer((host, port), handler_factory(application))
    server.daemon_threads = True
    return server, application


def serve_in_background(server: ThreadingHTTPServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, name="pyrenees-selects-http", daemon=True)
    thread.start()
    return thread


def run(host: str, port: int, data_dir: Path | None = None, default_source: str = "", open_browser: bool = True) -> None:
    server, application = create_local_server(data_dir, default_source, host, port)
    actual_port = server.server_address[1]
    url = f"http://localhost:{actual_port}"
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
