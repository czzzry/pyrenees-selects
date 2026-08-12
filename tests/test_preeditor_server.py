import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock

from pyrenees_selects.config import AppPaths
from pyrenees_selects.preeditor_server import Handler, SelectsApplication


class PreEditorServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        static = Path(__file__).resolve().parents[1] / "pyrenees_selects" / "static"
        paths = AppPaths(root=root, database=root / "selects.sqlite3", cache=root / "cache", static=static)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.application = SelectsApplication(paths)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def test_static_and_api_responses_have_local_security_headers(self) -> None:
        with urllib.request.urlopen(self.base + "/") as response:
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        with urllib.request.urlopen(self.base + "/api/projects") as response:
            self.assertEqual(json.loads(response.read()), {"projects": []})
            self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_mutations_require_json(self) -> None:
        request = urllib.request.Request(self.base + "/api/projects", data=b"name=test", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 400)

    def test_foreign_origin_cannot_change_a_local_project(self) -> None:
        request = urllib.request.Request(
            self.base + "/api/projects",
            data=json.dumps({"name": "Blocked", "target_duration_seconds": 120}).encode(),
            headers={"Content-Type": "application/json", "Origin": "https://attacker.example"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 403)
        with urllib.request.urlopen(self.base + "/api/projects") as response:
            self.assertEqual(json.loads(response.read()), {"projects": []})

    def test_foreign_host_is_blocked_even_for_reads(self) -> None:
        request = urllib.request.Request(self.base + "/api/projects", headers={"Host": "attacker.example"})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 403)

    def test_export_is_a_post_protected_by_origin_checks(self) -> None:
        export = Mock(return_value={"fcpxml": "/tmp/cut.fcpxml"})
        self.server.application.export = export

        foreign = urllib.request.Request(
            self.base + "/api/sequences/sequence-1/export",
            data=b"{}",
            headers={"Content-Type": "application/json", "Origin": "https://attacker.example"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(foreign)
        self.assertEqual(error.exception.code, 403)
        export.assert_not_called()

        local = urllib.request.Request(
            self.base + "/api/sequences/sequence-1/export",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(local) as response:
            self.assertEqual(response.status, 201)
            self.assertEqual(json.loads(response.read()), {"fcpxml": "/tmp/cut.fcpxml"})
        export.assert_called_once_with("sequence-1")

    def test_project_brief_api_persists_canonical_planning_fields(self) -> None:
        body = {
            "name": "Neutral project",
            "target_duration_seconds": 240,
            "shot_rhythm": "custom",
            "shot_min_seconds": 5,
            "shot_max_seconds": 11,
            "candidate_breadth": "broad",
            "audio_preference": "visual",
            "orientation": "portrait",
            "intent": "Build slowly toward a peak.",
        }
        request = urllib.request.Request(
            self.base + "/api/projects", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request) as response:
            project = json.loads(response.read())["project"]
        for key, value in body.items():
            self.assertEqual(project[key], value)


if __name__ == "__main__":
    unittest.main()
