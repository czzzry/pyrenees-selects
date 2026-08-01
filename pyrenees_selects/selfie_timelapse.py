from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .selfie_review import DEFAULT_INVENTORY, DEFAULT_SOURCE, DEFAULT_STATE, capture_time_from_filename, load_inventory


DEFAULT_OUTPUT = Path("/Volumes/Untitled/Pyrenees Selfie Timelapse/analysis/alignment-pilot")
DEFAULT_FULL_OUTPUT = Path("/Volumes/Untitled/Pyrenees Selfie Timelapse/analysis/face-aligned-v1")
DEFAULT_SWIFT_SOURCE = Path(__file__).resolve().parent.parent / "tools" / "vision_face_landmarks.swift"
EXIF_ORIENTATION = 274


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.partial")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def display_size(width: int, height: int, orientation: int) -> tuple[int, int]:
    return (height, width) if orientation in {5, 6, 7, 8} else (width, height)


def load_review_state(state_path: Path) -> dict[str, Any]:
    payload = json.loads(state_path.expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    reviews = payload.get("reviews")
    if not isinstance(reviews, dict):
        raise ValueError("The selfie review does not contain a reviews object.")
    return payload


def ensure_output_outside_source(output_dir: Path, source_dir: Path) -> Path:
    output = output_dir.expanduser().resolve()
    source = source_dir.expanduser().resolve(strict=True)
    if output == source or source in output.parents:
        raise ValueError("Pilot output must be outside the original photo folder.")
    return output


def build_manifest(
    source_dir: Path,
    inventory_path: Path,
    state_path: Path,
    *,
    include_hashes: bool = True,
) -> dict[str, Any]:
    source = source_dir.expanduser().resolve(strict=True)
    state = load_review_state(state_path)
    reviews = state["reviews"]
    photos = load_inventory(source, inventory_path)
    missing = [photo.filename for photo in photos if photo.filename not in reviews]
    if missing:
        raise ValueError(f"{len(missing)} inventory photos are missing from the completed review.")
    unknown = sorted(set(reviews) - {photo.filename for photo in photos})
    if unknown:
        raise ValueError(f"{len(unknown)} review records are not in the likely-selfie inventory.")

    records: list[dict[str, Any]] = []
    for photo in photos:
        stat = photo.path.stat()
        with Image.open(photo.path) as image:
            width, height = image.size
            orientation = int(image.getexif().get(EXIF_ORIENTATION, 1))
        shown_width, shown_height = display_size(width, height, orientation)
        review = reviews[photo.filename]
        record = {
            "index": photo.id,
            "filename": photo.filename,
            "path": str(photo.path),
            "captured_at": photo.captured_at,
            "decision": review.get("decision"),
            "comment": review.get("comment", ""),
            "byte_size": stat.st_size,
            "modified_ns": stat.st_mtime_ns,
            "pixel_width": width,
            "pixel_height": height,
            "display_width": shown_width,
            "display_height": shown_height,
            "exif_orientation": orientation,
        }
        if include_hashes:
            record["sha256"] = sha256_path(photo.path)
        records.append(record)

    return {
        "version": 1,
        "created_at": utc_now(),
        "source_dir": str(source),
        "inventory_path": str(inventory_path.expanduser().resolve(strict=True)),
        "review_state_path": str(state_path.expanduser().resolve(strict=True)),
        "review_updated_at": state.get("updated_at"),
        "photo_count": len(records),
        "photos": records,
    }


def load_face_geometry(inventory_path: Path, allowed: set[str]) -> dict[str, dict[str, float]]:
    geometry: dict[str, dict[str, float]] = {}
    with inventory_path.expanduser().resolve(strict=True).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = {"filename", "x", "y", "width", "height", "largest_area"}
        if not fields.issubset(reader.fieldnames or []):
            raise ValueError("The face inventory does not include geometry columns.")
        for row in reader:
            filename = row["filename"]
            if filename not in allowed:
                continue
            x = float(row["x"])
            y = float(row["y"])
            width = float(row["width"])
            height = float(row["height"])
            geometry[filename] = {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "area": float(row["largest_area"]),
                "cx": x + width / 2,
                "cy": y + height / 2,
                "edge": min(x, y, 1 - x - width, 1 - y - height),
            }
    return geometry


def _evenly_spaced(records: list[dict[str, Any]], count: int) -> Iterable[dict[str, Any]]:
    if count <= 1:
        yield records[len(records) // 2]
        return
    for position in range(count):
        yield records[round(position * (len(records) - 1) / (count - 1))]


def select_pilot(
    records: list[dict[str, Any]],
    geometry: dict[str, dict[str, float]],
    *,
    limit: int = 15,
) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("Pilot size must be positive.")
    by_name = {record["filename"]: record for record in records}
    selected: dict[str, set[str]] = {}

    def add(filename: str, reason: str) -> None:
        if filename in by_name and (filename in selected or len(selected) < limit):
            selected.setdefault(filename, set()).add(reason)

    for record in records:
        if record.get("comment"):
            add(record["filename"], "saved comment")
        if record.get("decision") != "include":
            add(record["filename"], f"decision: {record.get('decision') or 'pending'}")

    timeline = list(_evenly_spaced(records, 7))
    for position in (0, 6, 3):
        add(timeline[position]["filename"], "timeline sample")

    available = [name for name in by_name if name in geometry]
    if available:
        extrema = (
            ("furthest left", min(available, key=lambda name: geometry[name]["cx"])),
            ("furthest right", max(available, key=lambda name: geometry[name]["cx"])),
            ("highest face", min(available, key=lambda name: geometry[name]["cy"])),
            ("lowest face", max(available, key=lambda name: geometry[name]["cy"])),
            ("smallest face", min(available, key=lambda name: geometry[name]["area"])),
            ("largest face", max(available, key=lambda name: geometry[name]["area"])),
            ("closest to edge", min(available, key=lambda name: geometry[name]["edge"])),
        )
        for reason, filename in extrema:
            add(filename, reason)

    for position in (1, 2, 4, 5):
        add(timeline[position]["filename"], "timeline sample")
    for record in records:
        add(record["filename"], "timeline fill")
        if len(selected) >= limit:
            break

    selected_records = []
    for filename, reasons in selected.items():
        record = dict(by_name[filename])
        record["pilot_reasons"] = sorted(reasons)
        selected_records.append(record)
    selected_records.sort(key=lambda record: record["index"])
    return selected_records


def compile_vision_helper(swift_source: Path, cache_dir: Path) -> Path:
    source = swift_source.expanduser().resolve(strict=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    binary = cache_dir / "vision-face-landmarks"
    if not binary.exists() or binary.stat().st_mtime_ns < source.stat().st_mtime_ns:
        command = [
            "swiftc",
            str(source),
            "-framework",
            "Vision",
            "-framework",
            "ImageIO",
            "-o",
            str(binary),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)
    return binary


def run_vision(binary: Path, paths: list[Path], *, progress: bool = False) -> dict[str, Any]:
    command = [str(binary), *(str(path.expanduser().resolve(strict=True)) for path in paths)]
    result = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=None if progress else subprocess.PIPE,
        text=True,
        timeout=1200,
    )
    return json.loads(result.stdout)


def run_vision_batched(
    binary: Path,
    records: list[dict[str, Any]],
    checkpoint_path: Path,
    *,
    batch_size: int = 64,
) -> dict[str, Any]:
    checkpoint = {"version": 1, "results": [], "failures": []}
    if checkpoint_path.exists():
        saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if isinstance(saved.get("results"), list) and isinstance(saved.get("failures"), list):
            checkpoint = saved
    completed = {
        item["filename"]
        for item in [*checkpoint["results"], *checkpoint["failures"]]
        if isinstance(item, dict) and isinstance(item.get("filename"), str)
    }
    remaining = [record for record in records if record["filename"] not in completed]
    total_batches = math.ceil(len(remaining) / batch_size) if remaining else 0
    for start in range(0, len(remaining), batch_size):
        batch = remaining[start : start + batch_size]
        print(
            f"Vision batch {start // batch_size + 1}/{total_batches} · "
            f"{len(completed)}/{len(records)} already complete",
            flush=True,
        )
        payload = run_vision(binary, [Path(record["path"]) for record in batch], progress=True)
        checkpoint["results"].extend(payload.get("results", []))
        checkpoint["failures"].extend(payload.get("failures", []))
        checkpoint["updated_at"] = utc_now()
        atomic_json(checkpoint_path, checkpoint)
        completed.update(record["filename"] for record in batch)
    return checkpoint


@dataclass(frozen=True)
class AlignmentTransform:
    scale: float
    translate_x: float
    translate_y: float
    source_eye_midpoint_x: float
    source_eye_midpoint_y: float
    source_eye_distance: float
    target_eye_midpoint_x: float
    target_eye_midpoint_y: float
    target_eye_distance: float

    def payload(self) -> dict[str, float]:
        return {
            "scale": self.scale,
            "translate_x": self.translate_x,
            "translate_y": self.translate_y,
            "source_eye_midpoint_x": self.source_eye_midpoint_x,
            "source_eye_midpoint_y": self.source_eye_midpoint_y,
            "source_eye_distance": self.source_eye_distance,
            "target_eye_midpoint_x": self.target_eye_midpoint_x,
            "target_eye_midpoint_y": self.target_eye_midpoint_y,
            "target_eye_distance": self.target_eye_distance,
        }


def alignment_transform(
    width: int,
    height: int,
    left_eye: dict[str, float],
    right_eye: dict[str, float],
    *,
    canvas: int,
    target_x: float,
    target_y: float,
    target_eye_distance: float,
) -> AlignmentTransform:
    if min(width, height, canvas) <= 0:
        raise ValueError("Image and canvas dimensions must be positive.")
    eye_a = (float(left_eye["x"]) * width, float(left_eye["y"]) * height)
    eye_b = (float(right_eye["x"]) * width, float(right_eye["y"]) * height)
    eye_midpoint = ((eye_a[0] + eye_b[0]) / 2, (eye_a[1] + eye_b[1]) / 2)
    eye_distance = math.hypot(eye_a[0] - eye_b[0], eye_a[1] - eye_b[1])
    if eye_distance <= 0:
        raise ValueError("Detected eyes occupy the same position.")
    target_distance_pixels = target_eye_distance * canvas
    scale = target_distance_pixels / eye_distance
    target_midpoint = (target_x * canvas, target_y * canvas)
    return AlignmentTransform(
        scale=scale,
        translate_x=target_midpoint[0] - eye_midpoint[0] * scale,
        translate_y=target_midpoint[1] - eye_midpoint[1] * scale,
        source_eye_midpoint_x=eye_midpoint[0],
        source_eye_midpoint_y=eye_midpoint[1],
        source_eye_distance=eye_distance,
        target_eye_midpoint_x=target_midpoint[0],
        target_eye_midpoint_y=target_midpoint[1],
        target_eye_distance=target_distance_pixels,
    )


def soft_lock_transform(
    width: int,
    height: int,
    left_eye: dict[str, float],
    right_eye: dict[str, float],
    *,
    canvas: int,
    target_x: float,
    target_y: float,
    target_eye_distance: float,
    dead_zone_x: tuple[float, float] = (0.35, 0.65),
    dead_zone_y: tuple[float, float] = (0.32, 0.48),
    max_eye_distance: float = 0.18,
) -> tuple[AlignmentTransform, str]:
    strict = alignment_transform(
        width,
        height,
        left_eye,
        right_eye,
        canvas=canvas,
        target_x=target_x,
        target_y=target_y,
        target_eye_distance=target_eye_distance,
    )
    eye_x = strict.source_eye_midpoint_x
    eye_y = strict.source_eye_midpoint_y
    low_x, high_x = dead_zone_x
    low_y, high_y = dead_zone_y
    if not (0 <= low_x <= target_x <= high_x <= 1 and 0 <= low_y <= target_y <= high_y <= 1):
        raise ValueError("The desired eye target must be inside both dead zones.")

    fill_scale = max(
        strict.scale,
        canvas / width,
        canvas / height,
        low_x * canvas / eye_x,
        (1 - high_x) * canvas / (width - eye_x),
        low_y * canvas / eye_y,
        (1 - high_y) * canvas / (height - eye_y),
    )
    max_scale = max_eye_distance * canvas / strict.source_eye_distance
    if fill_scale > max_scale:
        return strict, "background-extension"

    feasible_x = (
        max(low_x * canvas, canvas - (width - eye_x) * fill_scale),
        min(high_x * canvas, eye_x * fill_scale),
    )
    feasible_y = (
        max(low_y * canvas, canvas - (height - eye_y) * fill_scale),
        min(high_y * canvas, eye_y * fill_scale),
    )
    target_pixels_x = min(max(target_x * canvas, feasible_x[0]), feasible_x[1])
    target_pixels_y = min(max(target_y * canvas, feasible_y[0]), feasible_y[1])
    return (
        AlignmentTransform(
            scale=fill_scale,
            translate_x=target_pixels_x - eye_x * fill_scale,
            translate_y=target_pixels_y - eye_y * fill_scale,
            source_eye_midpoint_x=eye_x,
            source_eye_midpoint_y=eye_y,
            source_eye_distance=strict.source_eye_distance,
            target_eye_midpoint_x=target_pixels_x,
            target_eye_midpoint_y=target_pixels_y,
            target_eye_distance=strict.source_eye_distance * fill_scale,
        ),
        "fill-first",
    )


def source_covers_canvas(width: int, height: int, transform: AlignmentTransform, canvas: int) -> bool:
    return (
        transform.translate_x <= 0
        and transform.translate_y <= 0
        and transform.translate_x + width * transform.scale >= canvas
        and transform.translate_y + height * transform.scale >= canvas
    )


def _oriented_image(path: Path) -> Image.Image:
    with Image.open(path) as source:
        return ImageOps.exif_transpose(source).convert("RGB")


def render_aligned(
    image: Image.Image,
    transform: AlignmentTransform,
    *,
    canvas: int,
) -> Image.Image:
    background = ImageOps.fit(image, (canvas, canvas), method=Image.Resampling.LANCZOS)
    background = background.filter(ImageFilter.GaussianBlur(radius=max(8, canvas // 36)))
    background = ImageEnhance.Brightness(background).enhance(0.62)
    resized = image.resize(
        (
            max(1, round(image.width * transform.scale)),
            max(1, round(image.height * transform.scale)),
        ),
        Image.Resampling.LANCZOS,
    )
    background.paste(resized, (round(transform.translate_x), round(transform.translate_y)))
    return background


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf") if bold else Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _draw_original_overlay(
    image: Image.Image,
    landmark: dict[str, Any],
    transform: AlignmentTransform,
    *,
    panel: int,
    canvas: int,
) -> Image.Image:
    result = Image.new("RGB", (panel, panel), "#121612")
    contained = ImageOps.contain(image, (panel, panel), method=Image.Resampling.LANCZOS)
    offset_x = (panel - contained.width) / 2
    offset_y = (panel - contained.height) / 2
    result.paste(contained, (round(offset_x), round(offset_y)))
    ratio = contained.width / image.width
    draw = ImageDraw.Draw(result)

    box = landmark["face_box"]
    face_left = offset_x + box["x"] * contained.width
    face_top = offset_y + box["y"] * contained.height
    face_right = face_left + box["width"] * contained.width
    face_bottom = face_top + box["height"] * contained.height
    draw.rectangle((face_left, face_top, face_right, face_bottom), outline="#e74b3c", width=4)

    for eye in (landmark["left_eye"], landmark["right_eye"]):
        x = offset_x + eye["x"] * contained.width
        y = offset_y + eye["y"] * contained.height
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill="#ccff33", outline="#111111", width=2)

    crop_left = (0 - transform.translate_x) / transform.scale
    crop_top = (0 - transform.translate_y) / transform.scale
    crop_right = (canvas - transform.translate_x) / transform.scale
    crop_bottom = (canvas - transform.translate_y) / transform.scale
    draw.rectangle(
        (
            offset_x + crop_left * ratio,
            offset_y + crop_top * ratio,
            offset_x + crop_right * ratio,
            offset_y + crop_bottom * ratio,
        ),
        outline="#54c7ec",
        width=3,
    )
    return result


def _draw_aligned_overlay(image: Image.Image, *, panel: int, target_x: float, target_y: float) -> Image.Image:
    result = image.resize((panel, panel), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(result)
    x = target_x * panel
    y = target_y * panel
    draw.line((x - 16, y, x + 16, y), fill="#ccff33", width=3)
    draw.line((x, y - 16, x, y + 16), fill="#ccff33", width=3)
    return result


def _contact_card(
    entry: dict[str, Any],
    original_overlay: Image.Image,
    aligned_overlay: Image.Image,
    *,
    panel: int,
) -> Image.Image:
    gap = 24
    label_height = 132
    width = panel * 2 + gap * 3
    height = panel + label_height + gap * 2
    card = Image.new("RGB", (width, height), "#f3efe6")
    card.paste(original_overlay, (gap, gap))
    card.paste(aligned_overlay, (panel + gap * 2, gap))
    draw = ImageDraw.Draw(card)
    title_font = _font(24, bold=True)
    body_font = _font(17)
    label_y = panel + gap + 10
    draw.text((gap, label_y), f'{entry["index"]:03d}  {entry["filename"]}', fill="#111111", font=title_font)
    metrics = (
        f'Quality {entry.get("face_capture_quality", 0):.3f}   '
        f'Vision confidence {entry.get("face_confidence", 0):.3f}   '
        f'scale {entry["transform"]["scale"]:.3f}×   '
        f'{entry["alignment_mode"]}'
    )
    draw.text((gap, label_y + 34), metrics, fill="#343a34", font=body_font)
    reasons = "Pilot reason: " + ", ".join(entry["pilot_reasons"])
    draw.text((gap, label_y + 60), reasons, fill="#343a34", font=body_font)
    comment = entry.get("comment", "").strip()
    if comment:
        wrapped = textwrap.shorten(comment, width=105, placeholder="…")
        draw.text((gap, label_y + 86), f"Saved note: {wrapped}", fill="#972f24", font=body_font)
    draw.text((panel + gap * 2, label_y - 30), "Proposed soft-lock frame", fill="#111111", font=body_font)
    draw.text((gap, label_y - 30), "Original · red face box · cyan crop", fill="#111111", font=body_font)
    return card


def _failure_card(
    selected_record: dict[str, Any],
    image: Image.Image,
    error: str,
    *,
    panel: int,
) -> Image.Image:
    gap = 24
    label_height = 132
    width = panel * 2 + gap * 3
    height = panel + label_height + gap * 2
    card = Image.new("RGB", (width, height), "#f3efe6")
    original = Image.new("RGB", (panel, panel), "#121612")
    contained = ImageOps.contain(image, (panel, panel), method=Image.Resampling.LANCZOS)
    original.paste(contained, ((panel - contained.width) // 2, (panel - contained.height) // 2))
    card.paste(original, (gap, gap))
    missing = Image.new("RGB", (panel, panel), "#20251f")
    missing_draw = ImageDraw.Draw(missing)
    missing_draw.text(
        (panel // 2, panel // 2 - 20),
        "NO RELIABLE LANDMARKS",
        anchor="mm",
        fill="#ffcbc1",
        font=_font(22, bold=True),
    )
    missing_draw.text(
        (panel // 2, panel // 2 + 22),
        "Manual crop, alternate detector, or removal",
        anchor="mm",
        fill="#f3efe6",
        font=_font(17),
    )
    card.paste(missing, (panel + gap * 2, gap))
    draw = ImageDraw.Draw(card)
    label_y = panel + gap + 10
    draw.text(
        (gap, label_y),
        f'{selected_record["index"]:03d}  {selected_record["filename"]}',
        fill="#111111",
        font=_font(24, bold=True),
    )
    draw.text(
        (gap, label_y + 34),
        "Vision landmark failure · correctly routed to the exception queue",
        fill="#972f24",
        font=_font(17),
    )
    reasons = "Pilot reason: " + ", ".join(selected_record["pilot_reasons"])
    draw.text((gap, label_y + 60), reasons, fill="#343a34", font=_font(17))
    draw.text(
        (gap, label_y + 86),
        textwrap.shorten(error, width=112, placeholder="…"),
        fill="#343a34",
        font=_font(17),
    )
    return card


def contact_sheets(cards: list[Image.Image], output_dir: Path, *, per_sheet: int = 5) -> list[Path]:
    paths: list[Path] = []
    for start in range(0, len(cards), per_sheet):
        group = cards[start : start + per_sheet]
        sheet = Image.new("RGB", (group[0].width, sum(card.height for card in group)), "#ded8cc")
        y = 0
        for card in group:
            sheet.paste(card, (0, y))
            y += card.height
        path = output_dir / f"contact-sheet-{start // per_sheet + 1}.jpg"
        sheet.save(path, quality=91, optimize=True)
        paths.append(path)
    return paths


def _diagnostic_frame(
    aligned: Image.Image,
    record: dict[str, Any],
    *,
    sequence_position: int,
    sequence_total: int,
    alignment_mode: str,
) -> Image.Image:
    frame = aligned.copy()
    bar_height = max(64, frame.height // 14)
    overlay = Image.new("RGBA", (frame.width, bar_height), (10, 13, 10, 196))
    draw = ImageDraw.Draw(overlay)
    left = (
        f'{sequence_position:03d}/{sequence_total:03d} · '
        f'source {record["index"]:03d} · {record["captured_at"].replace("T", " ")}'
    )
    right = alignment_mode
    draw.text((18, bar_height / 2), left, anchor="lm", fill="#f7f3ea", font=_font(22))
    draw.text((frame.width - 18, bar_height / 2), right, anchor="rm", fill="#ccff33", font=_font(20, bold=True))
    composited = frame.convert("RGBA")
    composited.alpha_composite(overlay, (0, frame.height - bar_height))
    frame.close()
    return composited.convert("RGB")


def encode_diagnostic_video(
    frames_dir: Path,
    destination: Path,
    *,
    image_count: int,
    photos_per_second: int = 8,
    output_fps: int = 24,
) -> Path:
    if image_count < 1:
        raise ValueError("At least one aligned frame is required.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required to encode the diagnostic video.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".partial.mp4")
    temporary.unlink(missing_ok=True)
    command = [
        ffmpeg,
        "-v",
        "error",
        "-framerate",
        str(photos_per_second),
        "-start_number",
        "1",
        "-i",
        str(frames_dir / "frame-%04d.jpg"),
        "-vf",
        f"fps={output_fps},format=yuv420p",
        "-frames:v",
        str(image_count * output_fps // photos_per_second),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-movflags",
        "+faststart",
        "-y",
        str(temporary),
    ]
    subprocess.run(command, check=True, timeout=1800)
    os.replace(temporary, destination)
    return destination


def probe_video(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("FFprobe is required to verify the diagnostic video.")
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate,nb_frames:format=duration,size",
        "-of",
        "json",
        str(path.expanduser().resolve(strict=True)),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
    return json.loads(result.stdout)


def run_full_diagnostic(
    *,
    source_dir: Path,
    inventory_path: Path,
    state_path: Path,
    output_dir: Path,
    swift_source: Path,
    excluded_filenames: set[str],
    canvas: int,
    target_x: float,
    target_y: float,
    target_eye_distance: float,
) -> dict[str, Any]:
    source = source_dir.expanduser().resolve(strict=True)
    output = ensure_output_outside_source(output_dir, source)
    output.mkdir(parents=True, exist_ok=True)

    print("Building checksummed source manifest…", flush=True)
    manifest = build_manifest(source, inventory_path, state_path)
    manifest_path = output / "source-manifest.json"
    atomic_json(manifest_path, manifest)
    known = {record["filename"] for record in manifest["photos"]}
    unknown_exclusions = excluded_filenames - known
    if unknown_exclusions:
        raise ValueError(f"Unknown technical exclusions: {', '.join(sorted(unknown_exclusions))}")

    active_records = [
        record
        for record in manifest["photos"]
        if record.get("decision") in {"include", "maybe"} and record["filename"] not in excluded_filenames
    ]
    technical_exclusions = {
        "version": 1,
        "created_at": utc_now(),
        "photos": [
            {
                "filename": filename,
                "reason": "User-approved technical removal: the face is already cropped at the image edge.",
            }
            for filename in sorted(excluded_filenames)
        ],
    }
    exclusions_path = output / "technical-exclusions.json"
    atomic_json(exclusions_path, technical_exclusions)

    binary = compile_vision_helper(swift_source, output / ".cache")
    vision_path = output / "vision-landmarks.json"
    vision = run_vision_batched(binary, active_records, vision_path)
    by_name = {result["filename"]: result for result in vision["results"]}
    failures_by_name = {failure["filename"]: failure for failure in vision["failures"]}

    renderable = [record for record in active_records if record["filename"] in by_name]
    aligned_dir = output / "aligned"
    diagnostic_dir = output / "diagnostic-frames"
    aligned_dir.mkdir(exist_ok=True)
    diagnostic_dir.mkdir(exist_ok=True)
    report_entries: list[dict[str, Any]] = []

    print(f"Rendering {len(renderable)} aligned diagnostic frames…", flush=True)
    for sequence_position, record in enumerate(renderable, start=1):
        landmark = by_name[record["filename"]]
        image = _oriented_image(Path(record["path"]))
        transform, alignment_mode = soft_lock_transform(
            image.width,
            image.height,
            landmark["left_eye"],
            landmark["right_eye"],
            canvas=canvas,
            target_x=target_x,
            target_y=target_y,
            target_eye_distance=target_eye_distance,
        )
        aligned_path = aligned_dir / f'{record["index"]:03d}-{Path(record["filename"]).stem}.jpg'
        if aligned_path.exists() and aligned_path.stat().st_size > 0:
            aligned = _oriented_image(aligned_path)
        else:
            aligned = render_aligned(image, transform, canvas=canvas)
            aligned.save(aligned_path, quality=95, optimize=True)

        diagnostic_path = diagnostic_dir / f"frame-{sequence_position:04d}.jpg"
        if not diagnostic_path.exists() or diagnostic_path.stat().st_size == 0:
            diagnostic = _diagnostic_frame(
                aligned,
                record,
                sequence_position=sequence_position,
                sequence_total=len(renderable),
                alignment_mode=alignment_mode,
            )
            diagnostic.save(diagnostic_path, quality=93, optimize=True)
            diagnostic.close()

        report_entries.append(
            {
                "sequence_position": sequence_position,
                "source_index": record["index"],
                "filename": record["filename"],
                "captured_at": record["captured_at"],
                "decision": record["decision"],
                "comment": record["comment"],
                "alignment_mode": alignment_mode,
                "background_extension": alignment_mode == "background-extension",
                "face_capture_quality": landmark.get("face_capture_quality"),
                "face_confidence": landmark.get("face_confidence"),
                "landmark_confidence": landmark.get("landmark_confidence"),
                "transform": transform.payload(),
                "aligned_path": str(aligned_path),
                "diagnostic_path": str(diagnostic_path),
            }
        )
        image.close()
        aligned.close()
        if sequence_position % 20 == 0 or sequence_position == len(renderable):
            print(f"Aligned {sequence_position}/{len(renderable)}", flush=True)

    exception_cards: list[Image.Image] = []
    active_by_name = {record["filename"]: record for record in active_records}
    for filename, failure in failures_by_name.items():
        record = dict(active_by_name[filename])
        record["pilot_reasons"] = ["full-batch Vision failure"]
        image = _oriented_image(Path(record["path"]))
        exception_cards.append(_failure_card(record, image, failure["error"], panel=540))
        image.close()
    exception_sheets = contact_sheets(exception_cards, output, per_sheet=5) if exception_cards else []

    video_path = output / "pyrenees-selfie-alignment-diagnostic-v1.mp4"
    print("Encoding diagnostic video…", flush=True)
    encode_diagnostic_video(diagnostic_dir, video_path, image_count=len(report_entries))
    probe = probe_video(video_path)

    report = {
        "version": 1,
        "created_at": utc_now(),
        "manifest_path": str(manifest_path),
        "technical_exclusions_path": str(exclusions_path),
        "vision_landmarks_path": str(vision_path),
        "reviewed_photo_count": len(manifest["photos"]),
        "technical_exclusion_count": len(excluded_filenames),
        "requested_alignment_count": len(active_records),
        "rendered_photo_count": len(report_entries),
        "vision_failure_count": len(failures_by_name),
        "vision_failures": list(failures_by_name.values()),
        "canvas": canvas,
        "photos_per_second": 8,
        "output_fps": 24,
        "frames_per_photo": 3,
        "target": {
            "eye_midpoint_x": target_x,
            "eye_midpoint_y": target_y,
            "eye_distance": target_eye_distance,
            "dead_zone_x": [0.35, 0.65],
            "dead_zone_y": [0.32, 0.48],
            "maximum_eye_distance": 0.18,
            "rotation": "disabled",
        },
        "entries": report_entries,
        "exception_sheets": [str(path) for path in exception_sheets],
        "video_path": str(video_path),
        "video_probe": probe,
    }
    report_path = output / "diagnostic-report.json"
    atomic_json(report_path, report)
    return {
        "manifest": manifest_path,
        "report": report_path,
        "video": video_path,
        "requested": len(active_records),
        "rendered": len(report_entries),
        "failures": len(failures_by_name),
        "exception_sheets": exception_sheets,
    }


def run_pilot(
    *,
    source_dir: Path,
    inventory_path: Path,
    state_path: Path,
    output_dir: Path,
    swift_source: Path,
    limit: int,
    canvas: int,
    target_x: float,
    target_y: float,
    target_eye_distance: float,
) -> dict[str, Any]:
    source = source_dir.expanduser().resolve(strict=True)
    output = ensure_output_outside_source(output_dir, source)
    output.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(source, inventory_path, state_path)
    manifest_path = output / "source-manifest.json"
    atomic_json(manifest_path, manifest)

    geometry = load_face_geometry(inventory_path, {record["filename"] for record in manifest["photos"]})
    selected = select_pilot(manifest["photos"], geometry, limit=limit)
    binary = compile_vision_helper(swift_source, output / ".cache")
    vision = run_vision(binary, [Path(record["path"]) for record in selected])
    by_name = {result["filename"]: result for result in vision["results"]}
    failures_by_name = {failure["filename"]: failure for failure in vision.get("failures", [])}

    aligned_dir = output / "aligned"
    overlay_dir = output / "overlays"
    aligned_dir.mkdir(exist_ok=True)
    overlay_dir.mkdir(exist_ok=True)
    report_entries: list[dict[str, Any]] = []
    cards: list[Image.Image] = []
    panel = 540

    for selected_record in selected:
        filename = selected_record["filename"]
        landmark = by_name.get(filename)
        if not landmark:
            image = _oriented_image(Path(selected_record["path"]))
            failure = failures_by_name.get(filename, {"error": "No landmark result was returned."})
            cards.append(_failure_card(selected_record, image, failure["error"], panel=panel))
            continue
        image = _oriented_image(Path(selected_record["path"]))
        transform, alignment_mode = soft_lock_transform(
            image.width,
            image.height,
            landmark["left_eye"],
            landmark["right_eye"],
            canvas=canvas,
            target_x=target_x,
            target_y=target_y,
            target_eye_distance=target_eye_distance,
        )
        covers = source_covers_canvas(image.width, image.height, transform, canvas)
        aligned = render_aligned(image, transform, canvas=canvas)
        aligned_path = aligned_dir / f"{selected_record['index']:03d}-{Path(filename).stem}.jpg"
        aligned.save(aligned_path, quality=94, optimize=True)

        original_overlay = _draw_original_overlay(
            image,
            landmark,
            transform,
            panel=panel,
            canvas=canvas,
        )
        overlay_path = overlay_dir / f"{selected_record['index']:03d}-{Path(filename).stem}.jpg"
        original_overlay.save(overlay_path, quality=92, optimize=True)
        aligned_overlay = _draw_aligned_overlay(
            aligned,
            panel=panel,
            target_x=transform.target_eye_midpoint_x / canvas,
            target_y=transform.target_eye_midpoint_y / canvas,
        )

        entry = {
            "index": selected_record["index"],
            "filename": filename,
            "captured_at": selected_record["captured_at"],
            "decision": selected_record["decision"],
            "comment": selected_record["comment"],
            "pilot_reasons": selected_record["pilot_reasons"],
            "face_box": landmark["face_box"],
            "left_eye": landmark["left_eye"],
            "right_eye": landmark["right_eye"],
            "face_confidence": landmark.get("face_confidence"),
            "landmark_confidence": landmark.get("landmark_confidence"),
            "face_capture_quality": landmark.get("face_capture_quality"),
            "transform": transform.payload(),
            "alignment_mode": alignment_mode,
            "background_extension": not covers,
            "aligned_path": str(aligned_path),
            "overlay_path": str(overlay_path),
        }
        report_entries.append(entry)
        cards.append(_contact_card(entry, original_overlay, aligned_overlay, panel=panel))

    sheets = contact_sheets(cards, output) if cards else []
    enriched_failures = []
    selected_by_name = {record["filename"]: record for record in selected}
    for failure in vision.get("failures", []):
        selected_record = selected_by_name.get(failure["filename"], {})
        enriched_failures.append(
            {
                **failure,
                "index": selected_record.get("index"),
                "decision": selected_record.get("decision"),
                "comment": selected_record.get("comment", ""),
                "pilot_reasons": selected_record.get("pilot_reasons", []),
            }
        )
    report = {
        "version": 1,
        "created_at": utc_now(),
        "manifest_path": str(manifest_path),
        "canvas": canvas,
        "target": {
            "eye_midpoint_x": target_x,
            "eye_midpoint_y": target_y,
            "eye_distance": target_eye_distance,
            "dead_zone_x": [0.35, 0.65],
            "dead_zone_y": [0.32, 0.48],
            "maximum_eye_distance": 0.18,
            "rotation": "disabled",
        },
        "selected_count": len(selected),
        "successful_count": len(report_entries),
        "failures": enriched_failures,
        "entries": report_entries,
        "contact_sheets": [str(path) for path in sheets],
    }
    report_path = output / "pilot-report.json"
    atomic_json(report_path, report)
    return {
        "manifest": manifest_path,
        "report": report_path,
        "contact_sheets": sheets,
        "selected": len(selected),
        "successful": len(report_entries),
        "failures": len(report["failures"]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a non-destructive face-alignment pilot for the Pyrenees selfies.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    pilot = subparsers.add_parser("pilot", help="Create the manifest and a representative landmark/alignment contact sheet.")
    pilot.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    pilot.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    pilot.add_argument("--state", type=Path, default=DEFAULT_STATE)
    pilot.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    pilot.add_argument("--swift-source", type=Path, default=DEFAULT_SWIFT_SOURCE)
    pilot.add_argument("--limit", type=int, default=15)
    pilot.add_argument("--canvas", type=int, default=1080)
    pilot.add_argument("--target-eye-x", type=float, default=0.5)
    pilot.add_argument("--target-eye-y", type=float, default=0.40)
    pilot.add_argument("--target-eye-distance", type=float, default=0.11)
    full = subparsers.add_parser("full", help="Align the reviewed batch and render a labeled diagnostic video.")
    full.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    full.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    full.add_argument("--state", type=Path, default=DEFAULT_STATE)
    full.add_argument("--output", type=Path, default=DEFAULT_FULL_OUTPUT)
    full.add_argument("--swift-source", type=Path, default=DEFAULT_SWIFT_SOURCE)
    full.add_argument("--exclude", action="append", default=[], help="Filename to remove as a technical exception.")
    full.add_argument("--canvas", type=int, default=1080)
    full.add_argument("--target-eye-x", type=float, default=0.5)
    full.add_argument("--target-eye-y", type=float, default=0.40)
    full.add_argument("--target-eye-distance", type=float, default=0.11)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "pilot":
        result = run_pilot(
            source_dir=args.source,
            inventory_path=args.inventory,
            state_path=args.state,
            output_dir=args.output,
            swift_source=args.swift_source,
            limit=args.limit,
            canvas=args.canvas,
            target_x=args.target_eye_x,
            target_y=args.target_eye_y,
            target_eye_distance=args.target_eye_distance,
        )
        print(f"Manifest: {result['manifest']}")
        print(
            f"Pilot: {result['successful']}/{result['selected']} successful; "
            f"{result['failures']} landmark failures"
        )
        for sheet in result["contact_sheets"]:
            print(f"Contact sheet: {sheet}")
        print(f"Report: {result['report']}")
    elif args.command == "full":
        result = run_full_diagnostic(
            source_dir=args.source,
            inventory_path=args.inventory,
            state_path=args.state,
            output_dir=args.output,
            swift_source=args.swift_source,
            excluded_filenames={Path(filename).name for filename in args.exclude},
            canvas=args.canvas,
            target_x=args.target_eye_x,
            target_y=args.target_eye_y,
            target_eye_distance=args.target_eye_distance,
        )
        print(
            f"Diagnostic: {result['rendered']}/{result['requested']} aligned; "
            f"{result['failures']} landmark exceptions"
        )
        print(f"Video: {result['video']}")
        for sheet in result["exception_sheets"]:
            print(f"Exception sheet: {sheet}")
        print(f"Report: {result['report']}")


if __name__ == "__main__":
    main()
