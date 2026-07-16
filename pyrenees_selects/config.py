from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path


def default_data_dir() -> Path:
    override = os.environ.get("PYRENEES_SELECTS_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Pyrenees Selects"
    return Path.home() / ".local" / "share" / "pyrenees-selects"


@dataclass(frozen=True)
class AppPaths:
    root: Path
    database: Path
    cache: Path
    static: Path

    @classmethod
    def build(cls, root: Path | None = None) -> "AppPaths":
        data_root = (root or default_data_dir()).expanduser().resolve()
        package_root = Path(__file__).parent
        return cls(
            root=data_root,
            database=data_root / "pyrenees-selects.sqlite3",
            cache=data_root / "cache",
            static=package_root / "static",
        )

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
