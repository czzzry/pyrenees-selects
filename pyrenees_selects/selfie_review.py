from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import re
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


DECISIONS = {"include", "maybe", "exclude"}
DEFAULT_SOURCE = Path("/Volumes/Untitled/Pyrenees Selfie Timelapse/trip-photos")
DEFAULT_INVENTORY = Path("/Volumes/Untitled/Pyrenees Selfie Timelapse/analysis/face-inventory.tsv")
DEFAULT_STATE = Path("/Volumes/Untitled/Pyrenees Selfie Timelapse/analysis/selfie-review.json")
FILENAME_TIME = re.compile(r"(?:PXL|IMG|P)_(\d{8})_(\d{6})", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def capture_time_from_filename(filename: str) -> tuple[str, str]:
    match = FILENAME_TIME.search(filename)
    if not match:
        return filename.casefold(), "Capture time unavailable"
    captured = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
    return captured.isoformat(), captured.strftime("%B %-d, %Y · %H:%M")


@dataclass(frozen=True)
class ReviewPhoto:
    id: int
    filename: str
    path: Path
    captured_at: str
    captured_label: str

    def payload(self, review: dict[str, Any] | None = None) -> dict[str, Any]:
        saved = review or {}
        return {
            "id": self.id,
            "filename": self.filename,
            "captured_at": self.captured_at,
            "captured_label": self.captured_label,
            "decision": saved.get("decision"),
            "comment": saved.get("comment", ""),
            "updated_at": saved.get("updated_at"),
            "image_url": f"/media/{self.id}.jpg",
        }


def load_inventory(source_dir: Path, inventory: Path) -> list[ReviewPhoto]:
    source = source_dir.expanduser().resolve(strict=True)
    if not source.is_dir():
        raise NotADirectoryError(str(source))
    inventory_path = inventory.expanduser().resolve(strict=True)
    records: list[tuple[str, str, Path]] = []
    with inventory_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"filename", "status"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("The face inventory is missing filename or status columns.")
        for row in reader:
            if row["status"] != "likely_selfie":
                continue
            filename = Path(row["filename"]).name
            candidate = (source / filename).resolve(strict=True)
            if candidate.parent != source:
                raise PermissionError(f"{filename} is outside the source folder.")
            captured_at, captured_label = capture_time_from_filename(filename)
            records.append((captured_at, captured_label, candidate))
    records.sort(key=lambda item: (item[0], item[2].name.casefold()))
    if not records:
        raise ValueError("The inventory contains no likely-selfie photos.")
    return [
        ReviewPhoto(index, path.name, path, captured_at, captured_label)
        for index, (captured_at, captured_label, path) in enumerate(records, start=1)
    ]


class ReviewStore:
    def __init__(self, state_path: Path, source_dir: Path):
        self.state_path = state_path.expanduser().resolve()
        self.source_dir = source_dir.expanduser().resolve(strict=True)
        self.lock = threading.RLock()
        self.reviews: dict[str, dict[str, Any]] = {}
        self.updated_at: str | None = None
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read the existing selfie review: {exc}") from exc
        raw_reviews = payload.get("reviews")
        if not isinstance(raw_reviews, dict):
            raise ValueError("The existing selfie review has an invalid reviews section.")
        for filename, value in raw_reviews.items():
            if not isinstance(value, dict):
                continue
            decision = value.get("decision")
            comment = value.get("comment", "")
            if decision is not None and decision not in DECISIONS:
                continue
            if not isinstance(comment, str):
                continue
            self.reviews[Path(filename).name] = {
                "decision": decision,
                "comment": comment[:2000],
                "updated_at": value.get("updated_at"),
            }
        self.updated_at = payload.get("updated_at")

    def review(self, filename: str) -> dict[str, Any]:
        with self.lock:
            return dict(self.reviews.get(filename, {}))

    def save(self, filename: str, *, decision: Any = ..., comment: Any = ...) -> dict[str, Any]:
        with self.lock:
            current = dict(self.reviews.get(filename, {}))
            if decision is not ...:
                if decision is not None and decision not in DECISIONS:
                    raise ValueError("Decision must be include, maybe, exclude, or empty.")
                current["decision"] = decision
            if comment is not ...:
                if not isinstance(comment, str):
                    raise ValueError("Comment must be text.")
                current["comment"] = comment[:2000]
            current.setdefault("decision", None)
            current.setdefault("comment", "")
            current["updated_at"] = utc_now()
            self.reviews[filename] = current
            self.updated_at = current["updated_at"]
            self._write()
            return dict(current)

    def _write(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "source_dir": str(self.source_dir),
            "updated_at": self.updated_at,
            "reviews": self.reviews,
        }
        temporary = self.state_path.with_suffix(f"{self.state_path.suffix}.partial")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.state_path)


class SelfieReviewApplication:
    def __init__(self, source_dir: Path, inventory: Path, state_path: Path, static_dir: Path | None = None):
        self.source_dir = source_dir.expanduser().resolve(strict=True)
        self.photos = load_inventory(self.source_dir, inventory)
        self.photos_by_id = {photo.id: photo for photo in self.photos}
        self.store = ReviewStore(state_path, self.source_dir)
        self.static_dir = (static_dir or Path(__file__).parent / "static").resolve(strict=True)

    def summary(self) -> dict[str, int]:
        counts = {"include": 0, "maybe": 0, "exclude": 0}
        for photo in self.photos:
            decision = self.store.review(photo.filename).get("decision")
            if decision in counts:
                counts[decision] += 1
        reviewed = sum(counts.values())
        return {
            "total": len(self.photos),
            "reviewed": reviewed,
            "remaining": len(self.photos) - reviewed,
            **counts,
        }

    def state_payload(self) -> dict[str, Any]:
        return {
            "photos": [photo.payload(self.store.review(photo.filename)) for photo in self.photos],
            "summary": self.summary(),
            "state_path": str(self.store.state_path),
        }

    def save_photo(self, photo_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        photo = self.photos_by_id.get(photo_id)
        if not photo:
            raise KeyError(photo_id)
        decision = payload["decision"] if "decision" in payload else ...
        comment = payload["comment"] if "comment" in payload else ...
        saved = self.store.save(photo.filename, decision=decision, comment=comment)
        return {"photo": photo.payload(saved), "summary": self.summary()}

    def photo_path(self, photo_id: int) -> Path:
        photo = self.photos_by_id.get(photo_id)
        if not photo:
            raise KeyError(photo_id)
        resolved = photo.path.resolve(strict=True)
        if resolved.parent != self.source_dir:
            raise PermissionError("Photo is outside the configured source folder.")
        return resolved


def _local_host(value: str) -> bool:
    host = value.partition(":")[0].strip("[]").casefold()
    return host in {"127.0.0.1", "localhost", "::1"}


def create_handler(application: SelfieReviewApplication) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "PyreneesSelfieReview/1"

        def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            self._send_json({"error": message}, status)

        def _send_file(self, path: Path, content_type: str, *, immutable: bool = False) -> None:
            try:
                body = path.read_bytes()
            except OSError:
                self._send_error(HTTPStatus.NOT_FOUND, "The requested file is unavailable.")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header(
                "Cache-Control",
                "private, max-age=31536000, immutable" if immutable else "no-cache",
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _valid_host(self) -> bool:
            return _local_host(self.headers.get("Host", ""))

        def do_GET(self) -> None:
            if not self._valid_host():
                self._send_error(HTTPStatus.FORBIDDEN, "This reviewer is available only on this Mac.")
                return
            path = urlsplit(self.path).path
            if path in {"/", "/index.html"}:
                self._send_file(application.static_dir / "selfie-review.html", "text/html; charset=utf-8")
                return
            if path == "/selfie-review.css":
                self._send_file(application.static_dir / "selfie-review.css", "text/css; charset=utf-8")
                return
            if path == "/selfie-review.js":
                self._send_file(
                    application.static_dir / "selfie-review.js",
                    "text/javascript; charset=utf-8",
                )
                return
            if path == "/api/state":
                self._send_json(application.state_payload())
                return
            match = re.fullmatch(r"/media/(\d+)\.jpg", path)
            if match:
                try:
                    asset = application.photo_path(int(match.group(1)))
                except (KeyError, OSError, PermissionError):
                    self._send_error(HTTPStatus.NOT_FOUND, "That review photo is unavailable.")
                    return
                media_type = mimetypes.guess_type(asset.name)[0] or "image/jpeg"
                self._send_file(asset, media_type, immutable=True)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "The requested page does not exist.")

        def do_POST(self) -> None:
            if not self._valid_host():
                self._send_error(HTTPStatus.FORBIDDEN, "This reviewer is available only on this Mac.")
                return
            path = urlsplit(self.path).path
            match = re.fullmatch(r"/api/photos/(\d+)", path)
            if not match:
                self._send_error(HTTPStatus.NOT_FOUND, "The requested action does not exist.")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_error(HTTPStatus.BAD_REQUEST, "The request size is invalid.")
                return
            if length <= 0 or length > 32_768:
                self._send_error(HTTPStatus.BAD_REQUEST, "The review update is empty or too large.")
                return
            try:
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Review update must be an object.")
                result = application.save_photo(int(match.group(1)), payload)
            except KeyError:
                self._send_error(HTTPStatus.NOT_FOUND, "That review photo is unavailable.")
                return
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json(result)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def create_server(
    source_dir: Path,
    inventory: Path,
    state_path: Path,
    *,
    port: int = 8753,
    static_dir: Path | None = None,
) -> tuple[ThreadingHTTPServer, SelfieReviewApplication]:
    application = SelfieReviewApplication(source_dir, inventory, state_path, static_dir)
    server = ThreadingHTTPServer(("127.0.0.1", port), create_handler(application))
    return server, application


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review likely Pyrenees selfies locally.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--port", type=int, default=8753)
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    server, application = create_server(
        arguments.source,
        arguments.inventory,
        arguments.state,
        port=arguments.port,
    )
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Pyrenees Selfie Review · {len(application.photos)} photos")
    print(f"Decisions and comments: {application.store.state_path}")
    print(url)
    if not arguments.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
