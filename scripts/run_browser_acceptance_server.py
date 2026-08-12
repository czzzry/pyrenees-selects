from __future__ import annotations

import shutil
import os
from pathlib import Path

from pyrenees_selects.preeditor_server import serve


port = int(os.environ.get("SELECTS_BROWSER_PORT", "8976"))
root = Path(f".tmp-browser-acceptance-{port}").resolve()
if root.exists():
    shutil.rmtree(root)
(root / "empty-footage").mkdir(parents=True)
serve(host="127.0.0.1", port=port, data_dir=root, open_browser=False)
