import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
