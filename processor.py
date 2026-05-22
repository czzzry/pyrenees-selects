from __future__ import annotations

import csv
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any


def export_remote_job_package(
    package_dir: Path,
    job_config: dict[str, Any],
    video_rows: list[dict[str, Any]],
    requirements_path: Path,
) -> dict[str, Path]:
    package_dir.mkdir(parents=True, exist_ok=True)

    job_config_path = package_dir / "job_config.json"
    manifest_path = package_dir / "selected_files_manifest.csv"
    environment_path = package_dir / "environment_requirements.txt"
    readme_path = package_dir / "README_remote_run.md"

    enriched_config = dict(job_config)
    enriched_config["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    job_config_path.write_text(json.dumps(enriched_config, indent=2), encoding="utf-8")

    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "filename",
                "absolute_local_path",
                "file_size",
                "duration",
                "resolution",
                "selected",
            ],
        )
        writer.writeheader()
        for row in video_rows:
            path = Path(str(row.get("path", ""))).expanduser()
            size = path.stat().st_size if path.exists() else ""
            writer.writerow(
                {
                    "filename": row.get("filename", path.name),
                    "absolute_local_path": str(path.resolve()) if path.exists() else str(path),
                    "file_size": size,
                    "duration": row.get("duration", ""),
                    "resolution": row.get("resolution", ""),
                    "selected": "yes" if row.get("include") else "no",
                }
            )

    requirements = requirements_path.read_text(encoding="utf-8") if requirements_path.exists() else ""
    environment_path.write_text(
        "\n".join(
            [
                "Environment Requirements",
                "========================",
                f"Python version used locally: {platform.python_version()}",
                f"Python executable used locally: {sys.executable}",
                "",
                "Required Python packages:",
                requirements.strip() or "- See project requirements.txt",
                "",
                "System requirements:",
                "- ffmpeg and ffprobe installed and available on PATH",
                "- Enough local disk space for raw footage, rendered clips, and outputs",
                "",
                "Expected folder structure:",
                "- raw_footage/ or equivalent mounted footage folder",
                "- music_library/ if using auto-selected music",
                "- outputs/",
                "- cache/analysis_cache/",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    readme_path.write_text(
        """# Remote Job Package

This package is a future remote execution handoff for the Drone Hiking Rough Cut app. It does not connect to any cloud provider by itself.

Privacy and cost warning:

- Remote processing may upload private footage to an external machine.
- Use only providers and machines you trust.
- Understand storage, transfer, and compute costs before running large video jobs.

What is included:

- `job_config.json`: selected settings and local file references.
- `selected_files_manifest.csv`: selected and unselected source video metadata.
- `environment_requirements.txt`: Python/package/ffmpeg expectations.
- `README_remote_run.md`: this guide.

What is not included:

- Raw video files are not included unless you copy them manually.
- Music files are not included unless you copy them manually.
- Cached analysis files are not included unless you copy `cache/analysis_cache/`.

Suggested remote setup:

1. Copy the project code to the remote machine.
2. Recreate the folder structure listed in `environment_requirements.txt`.
3. Copy raw footage to the same paths if possible, or update `job_config.json` paths.
4. Install Python dependencies with `pip install -r requirements.txt`.
5. Install ffmpeg and ffprobe.
6. Run `streamlit run app.py` on the remote machine, or use this package as the input for a future worker CLI.

This project is local-first today. Provider-specific remote execution is intentionally not implemented yet.
""",
        encoding="utf-8",
    )

    return {
        "job_config": job_config_path,
        "manifest": manifest_path,
        "environment": environment_path,
        "readme": readme_path,
    }
