from __future__ import annotations

import argparse
import json
import mimetypes
import sqlite3
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .config import AppPaths
from .assistant import propose_sequence
from .media import MediaToolError
from .preeditor import PreEditor, ProjectOptions, SelectionDraft
from .sequence_export import render_preview, write_handoff
from .server import ALLOWED_HOSTS, MAX_JSON_BYTES, parse_byte_range


def _public_source(source: dict[str, Any]) -> dict[str, Any]:
    payload = dict(source)
    payload.pop("current_path", None)
    payload.pop("fingerprint", None)
    payload["media_url"] = f"/api/sources/{source['id']}/media"
    return payload


def _public_selection(selection: dict[str, Any]) -> dict[str, Any]:
    payload = dict(selection)
    payload.pop("current_path", None)
    payload["media_url"] = f"/api/sources/{selection['source_id']}/media"
    return payload


def _public_version(version: dict[str, Any]) -> dict[str, Any]:
    payload = dict(version)
    payload["items"] = [_public_selection(item) for item in version.get("items") or []]
    return payload


class SelectsApplication:
    def __init__(self, paths: AppPaths):
        paths.ensure()
        self.paths = paths
        self.editor = PreEditor(paths.database)
        self.preview_lock = threading.Lock()

    def project_payload(self, project_id: str) -> dict[str, Any]:
        project = self.editor.project(project_id)
        if not project:
            raise KeyError(project_id)
        sources = self.editor.sources(project_id)
        selections = self.editor.selections(project_id)
        return {
            "project": project,
            "roots": [{key: value for key, value in root.items() if key != "path"} for root in self.editor.source_roots(project_id)],
            "sources": [_public_source(source) for source in sources],
            "selections": [_public_selection(selection) for selection in selections],
            "sequences": self.editor.sequences(project_id),
            "proposals": self.editor.proposals(project_id),
            "summary": {
                "source_count": len(sources),
                "ready_count": sum(source["status"] == "ready" for source in sources),
                "reviewed_count": len({selection["source_id"] for selection in selections}),
                "keep_seconds": sum(selection["duration"] for selection in selections if selection["decision"] == "keep"),
            },
        }

    def preview(self, sequence_id: str) -> Path:
        version = self.editor.latest_sequence_version(sequence_id)
        destination = self.paths.cache / "preeditor" / f"{version['id']}.mp4"
        with self.preview_lock:
            if not destination.is_file() or destination.stat().st_size == 0:
                render_preview(version, destination)
        return destination

    def export(self, sequence_id: str) -> dict[str, str]:
        version = self.editor.latest_sequence_version(sequence_id)
        project = self.editor.project(version["project_id"])
        if not project:
            raise KeyError(version["project_id"])
        destination = self.paths.root / "exports" / project["id"] / f"v{version['version']}"
        return write_handoff(
            version, destination, project_name=project["name"],
            orientation=project.get("orientation") if project.get("orientation") != "undecided" else "landscape",
        )


class Handler(BaseHTTPRequestHandler):
    server_version = "Selects/0.7"

    @property
    def app(self) -> SelectsApplication:
        return self.server.application  # type: ignore[attr-defined]

    def _host_allowed(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0]
        return host in ALLOWED_HOSTS

    def _json_body(self) -> dict[str, Any]:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Requests that change a project must use application/json.")
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid request length.") from exc
        if size <= 0 or size > MAX_JSON_BYTES:
            raise ValueError("Request body is empty or too large.")
        payload = json.loads(self.rfile.read(size))
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        super().end_headers()

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, path: Path, *, content_type: str | None = None, attachment: bool = False) -> None:
        resolved = path.resolve(strict=True)
        size = resolved.stat().st_size
        byte_range = parse_byte_range(self.headers.get("Range"), size)
        start, end = byte_range or (0, size - 1)
        self.send_response(HTTPStatus.PARTIAL_CONTENT if byte_range else HTTPStatus.OK)
        self.send_header("Content-Type", content_type or mimetypes.guess_type(resolved.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if byte_range:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{resolved.name}"')
        self.end_headers()
        with resolved.open("rb") as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    # Video players routinely abandon a Range request while
                    # scrubbing or switching sources. That is not an app error.
                    return
                remaining -= len(chunk)

    def _serve_static(self, name: str) -> None:
        allowed = {"preeditor.html", "preeditor.css", "preeditor.js"}
        if name not in allowed:
            raise FileNotFoundError(name)
        self._serve_file(self.app.paths.static / name)

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        try:
            path = unquote(urlparse(self.path).path)
            parts = [part for part in path.split("/") if part]
            if path == "/":
                self._serve_static("preeditor.html")
            elif path in {"/preeditor.css", "/preeditor.js"}:
                self._serve_static(path[1:])
            elif path == "/api/projects":
                self._send_json({"projects": self.app.editor.projects()})
            elif len(parts) == 3 and parts[:2] == ["api", "projects"]:
                self._send_json(self.app.project_payload(parts[2]))
            elif len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "context":
                self._send_json(self.app.editor.project_context(parts[2]))
            elif len(parts) == 4 and parts[:2] == ["api", "sources"] and parts[3] == "media":
                source = self.app.editor.source(parts[2])
                if not source or source["status"] != "ready":
                    raise FileNotFoundError(parts[2])
                self._serve_file(Path(source["current_path"]))
            elif len(parts) == 3 and parts[:2] == ["api", "sequences"]:
                self._send_json(_public_version(self.app.editor.latest_sequence_version(parts[2])))
            elif len(parts) == 4 and parts[:2] == ["api", "sequences"] and parts[3] == "preview":
                self._serve_file(self.app.preview(parts[2]), content_type="video/mp4")
            elif len(parts) == 4 and parts[:2] == ["api", "sequences"] and parts[3] == "export":
                self._send_json(self.app.export(parts[2]))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (KeyError, FileNotFoundError):
            self.send_error(HTTPStatus.NOT_FOUND)
        except (ValueError, OSError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (MediaToolError, sqlite3.Error) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
        except Exception as exc:
            print(f"Selects request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            self._send_json({"error": "Selects could not complete that request."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:  # noqa: N802
        if not self._host_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        try:
            path = unquote(urlparse(self.path).path)
            parts = [part for part in path.split("/") if part]
            body = self._json_body()
            if path == "/api/projects":
                project = self.app.editor.create_project(ProjectOptions(
                    str(body.get("name") or "Untitled project"),
                    float(body["target_duration"]) if body.get("target_duration") else None,
                    str(body.get("orientation") or "undecided"),
                    str(body.get("intent") or ""),
                    float(body.get("ideal_clip_duration") or 8),
                ))
                if body.get("source_path"):
                    self.app.editor.add_source_root(project["id"], Path(str(body["source_path"])))
                    self.app.editor.scan(project["id"])
                self._send_json(self.app.project_payload(project["id"]), HTTPStatus.CREATED)
            elif len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "roots":
                root = self.app.editor.add_source_root(
                    parts[2], Path(str(body.get("path") or "")), label=str(body.get("label") or ""),
                    recursive=bool(body.get("recursive", True)),
                )
                self._send_json({key: value for key, value in root.items() if key != "path"}, HTTPStatus.CREATED)
            elif len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "scan":
                result = self.app.editor.scan(parts[2])
                result["sources"] = [_public_source(source) for source in result["sources"]]
                self._send_json(result)
            elif len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "backup":
                backup = self.app.editor.backup_database()
                self._send_json({"backup": str(backup)})
            elif path == "/api/selections":
                draft = SelectionDraft(
                    source_id=str(body["source_id"]), in_seconds=float(body["in_seconds"]),
                    out_seconds=float(body["out_seconds"]), decision=str(body.get("decision") or "maybe"),
                    comment=str(body.get("comment") or ""), story_role=body.get("story_role"),
                    audio_intent=str(body.get("audio_intent") or "undecided"), origin="user",
                )
                selection = self.app.editor.create_selection(str(body["project_id"]), draft)
                self._send_json(_public_selection(selection), HTTPStatus.CREATED)
            elif len(parts) == 4 and parts[:2] == ["api", "selections"] and parts[3] == "markers":
                self._send_json(self.app.editor.add_marker(parts[2], float(body["source_seconds"]), str(body["comment"])), HTTPStatus.CREATED)
            elif path == "/api/sequences":
                sequence = self.app.editor.create_sequence(
                    str(body["project_id"]), str(body.get("name") or "First cut"), list(body.get("selection_ids") or []),
                    target_duration=float(body["target_duration"]) if body.get("target_duration") else None,
                    note=str(body.get("note") or "Initial sequence"),
                )
                self._send_json(_public_version(sequence), HTTPStatus.CREATED)
            elif len(parts) == 4 and parts[:2] == ["api", "sequences"] and parts[3] == "versions":
                version = self.app.editor.revise_sequence(parts[2], list(body.get("selection_ids") or []), note=str(body.get("note") or ""))
                self._send_json(_public_version(version), HTTPStatus.CREATED)
            elif path == "/api/proposals":
                self._send_json(self.app.editor.create_proposal(
                    str(body["project_id"]), provider=str(body.get("provider") or "external-agent"),
                    model=str(body.get("model") or ""), kind=str(body["kind"]), payload=body.get("payload") or {},
                    explanation=str(body.get("explanation") or ""),
                ), HTTPStatus.CREATED)
            elif len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "assist":
                proposal = propose_sequence(
                    self.app.editor.project_context(parts[2]), api_key=str(body.get("api_key") or ""),
                    model=str(body.get("model") or "gpt-5-mini"),
                    user_direction=str(body.get("direction") or ""),
                )
                saved = self.app.editor.create_proposal(
                    parts[2], provider=proposal["provider"], model=proposal["model"], kind=proposal["kind"],
                    payload=proposal["payload"], explanation=proposal["explanation"],
                )
                self._send_json(saved, HTTPStatus.CREATED)
            elif len(parts) == 4 and parts[:2] == ["api", "proposals"] and parts[3] == "apply":
                applied = self.app.editor.apply_proposal(parts[2])
                if isinstance(applied.get("result"), dict) and "items" in applied["result"]:
                    applied["result"] = _public_version(applied["result"])
                self._send_json(applied)
            elif len(parts) == 4 and parts[:2] == ["api", "proposals"] and parts[3] == "reject":
                self._send_json(self.app.editor.decide_proposal(parts[2], "rejected"))
            elif len(parts) == 4 and parts[:2] == ["api", "selections"] and parts[3] == "archive":
                self._send_json(_public_selection(self.app.editor.archive_selection(parts[2])))
            elif len(parts) == 4 and parts[:2] == ["api", "sources"] and parts[3] == "relink":
                self._send_json(_public_source(self.app.editor.relink_source(parts[2], Path(str(body.get("path") or "")))))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except KeyError as exc:
            self._send_json({"error": f"Not found: {exc}"}, HTTPStatus.NOT_FOUND)
        except (ValueError, TypeError, json.JSONDecodeError, OSError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (MediaToolError, sqlite3.Error) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
        except Exception as exc:
            print(f"Selects request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            self._send_json({"error": "Selects could not complete that request."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_PATCH(self) -> None:  # noqa: N802
        if not self._host_allowed():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        try:
            parts = [part for part in unquote(urlparse(self.path).path).split("/") if part]
            body = self._json_body()
            if len(parts) == 3 and parts[:2] == ["api", "selections"]:
                self._send_json(_public_selection(self.app.editor.update_selection(parts[2], **body)))
            elif len(parts) == 3 and parts[:2] == ["api", "projects"]:
                self._send_json(self.app.editor.update_project(parts[2], **body))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except KeyError as exc:
            self._send_json({"error": f"Not found: {exc}"}, HTTPStatus.NOT_FOUND)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except sqlite3.Error as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: object) -> None:
        return


def serve(*, host: str = "127.0.0.1", port: int = 8741, data_dir: Path | None = None, open_browser: bool = True) -> None:
    paths = AppPaths.build_selects(data_dir)
    server = ThreadingHTTPServer((host, port), Handler)
    server.application = SelectsApplication(paths)  # type: ignore[attr-defined]
    url = f"http://{host}:{server.server_port}/"
    print(f"Selects is ready at {url}")
    if open_browser:
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the reusable Selects pre-editor.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8741)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    serve(host=args.host, port=args.port, data_dir=args.data_dir, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
