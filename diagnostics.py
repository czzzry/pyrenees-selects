from __future__ import annotations

from pathlib import Path


def latest_performance_report_text(outputs_dir: Path) -> str:
    report = outputs_dir / "performance_report.txt"
    return report.read_text(encoding="utf-8") if report.exists() else ""
