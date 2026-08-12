from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from .media import VideoMetadata, probe_video, require_media_tools
from .preeditor import PreEditor, ProjectOptions, SelectionDraft


SAMPLE_NAME = "Sample · Coastal weekend"
SAMPLE_CLIPS = (
    ("morning-light.mp4", 28, 0.72, 392),
    ("coast-path.mp4", 108, 0.62, 523),
    ("train-arrival.mp4", 198, 0.55, 196),
)


def generate_sample_footage(destination: Path, *, ffmpeg: str | None = None) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    tool = ffmpeg or require_media_tools()[0]
    outputs: list[Path] = []
    for filename, hue, saturation, frequency in SAMPLE_CLIPS:
        output = destination / filename
        outputs.append(output)
        if output.is_file() and output.stat().st_size > 0:
            continue
        temporary = output.with_suffix(".partial.mp4")
        temporary.unlink(missing_ok=True)
        command = [
            tool, "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=24:duration=12",
            "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=48000:duration=12",
            "-vf", f"hue=h={hue}:s={saturation}",
            "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart", "-y", str(temporary),
        ]
        subprocess.run(command, check=True, capture_output=True, timeout=180)
        temporary.replace(output)
    return outputs


def ensure_sample_project(
    editor: PreEditor,
    data_root: Path,
    *,
    generator: Callable[[Path], list[Path]] = generate_sample_footage,
    probe: Callable[[Path], VideoMetadata] = probe_video,
) -> dict:
    for project in editor.projects():
        if project["name"] == SAMPLE_NAME and editor.sources(project["id"]):
            return project

    footage = data_root.expanduser().resolve() / "sample-footage"
    generator(footage)
    project = editor.create_project(ProjectOptions(
        SAMPLE_NAME,
        target_duration=18,
        orientation="landscape",
        intent="A small sample that teaches exact ranges, comments, alternates, and a first cut.",
        ideal_clip_duration=6,
    ))
    editor.add_source_root(project["id"], footage, label="Built-in sample", recursive=False)
    result = editor.scan(project["id"], probe=probe)
    sources = sorted((source for source in result["sources"] if source["status"] == "ready"), key=lambda item: item["filename"])
    if len(sources) < 3:
        raise RuntimeError("The sample project could not prepare its three demonstration clips.")
    # Leave the first alphabetic source undecided so onboarding can teach one
    # real selection while the other two demonstrate comments and assembly.
    drafts = (
        SelectionDraft(sources[1]["id"], 1, 7, "keep", "Hold through the full movement.", "opening", "background"),
        SelectionDraft(sources[2]["id"], 3, 9, "keep", "Keep the sound as the train arrives.", "ending", "preserve"),
    )
    selections = [editor.create_selection(project["id"], draft) for draft in drafts]
    editor.create_sequence(project["id"], "Sample first cut", [item["id"] for item in selections], note="Built-in onboarding sample")
    return project
