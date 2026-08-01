from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path


def default_data_dir() -> Path:
    override = os.environ.get("PYRENEES_SELECTS_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Pyrenees Selects"
    return Path.home() / ".local" / "share" / "pyrenees-selects"


def selects_data_dir() -> Path:
    override = os.environ.get("SELECTS_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Selects"
    return Path.home() / ".local" / "share" / "selects"


def bundled_resource_dir() -> Path | None:
    """Return py2app's Resources directory when running as a frozen Mac app."""
    configured = os.environ.get("RESOURCEPATH")
    if configured:
        resource_dir = Path(configured).expanduser().resolve()
        if resource_dir.is_dir():
            return resource_dir
    if getattr(sys, "frozen", False):
        resource_dir = Path(sys.executable).resolve().parent.parent / "Resources"
        if resource_dir.is_dir():
            return resource_dir
    return None


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
        resources = bundled_resource_dir()
        static_root = resources / "static" if resources and (resources / "static").is_dir() else package_root / "static"
        return cls(
            root=data_root,
            database=data_root / "pyrenees-selects.sqlite3",
            cache=data_root / "cache",
            static=static_root,
        )

    @classmethod
    def build_selects(cls, root: Path | None = None) -> "AppPaths":
        data_root = (root or selects_data_dir()).expanduser().resolve()
        legacy_shape = cls.build(data_root)
        return cls(
            root=data_root,
            database=data_root / "selects.sqlite3",
            cache=data_root / "cache",
            static=legacy_shape.static,
        )

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
