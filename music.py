from __future__ import annotations

from pathlib import Path


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


def is_supported_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTENSIONS
