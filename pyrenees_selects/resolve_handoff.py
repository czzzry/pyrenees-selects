from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.etree import ElementTree as ET


TIMELINE_FRAME_RATE = Fraction(30_000, 1_001)
TIMELINE_FRAME_DURATION = Fraction(1_001, 30_000)


@dataclass(frozen=True)
class SourceMedia:
    candidate_id: int
    path: Path
    duration: float
    width: int
    height: int
    fps: float


def frame_duration(fps: float) -> Fraction:
    if abs(fps - 29.97) < 0.02:
        return Fraction(1_001, 30_000)
    if abs(fps - 25.0) < 0.02:
        return Fraction(1, 25)
    return Fraction(1, round(fps))


def quantized_time(seconds: float, unit: Fraction) -> Fraction:
    frames = round(Fraction(str(seconds)) / unit)
    return frames * unit


def fcpx_time(value: Fraction) -> str:
    if value.denominator == 1:
        return f"{value.numerator}s"
    return f"{value.numerator}/{value.denominator}s"


def _format_id(media: SourceMedia) -> str:
    if media.width == 1_920 and media.height == 1_080:
        return "r4"
    return "r2" if abs(media.fps - 29.97) < 0.02 else "r3"


def _treatment_summary(item: Mapping[str, Any]) -> str:
    if item.get("signature_moment"):
        return "Approved extended bird master; preserve the original C78 source as the recovery reference"
    treatments: list[str] = []
    rate = float(item.get("playback_rate", 1.0))
    if abs(rate - 1.0) > 0.001:
        treatments.append(f"{rate * 100:.0f}% speed")
    if item.get("stabilize"):
        treatments.append("stabilize")
    crop_scale = float(item.get("crop_scale", 1.0))
    if abs(crop_scale - 1.0) > 0.001:
        treatments.append(f"center crop to {crop_scale * 100:.0f}%")
    contrast = float(item.get("contrast", 1.0))
    if abs(contrast - 1.0) > 0.001:
        treatments.append(f"contrast {contrast:.2f}")
    saturation = float(item.get("saturation", 1.0))
    if abs(saturation - 1.0) > 0.001:
        treatments.append(f"saturation {saturation:.2f}")
    if item.get("motion_interpolation"):
        treatments.append("optical flow")
    zoom_strength = float(item.get("zoom_strength", 0.0))
    if zoom_strength > 0.001:
        treatments.append(f"eased zoom {zoom_strength:.2f}")
    return " · ".join(treatments) if treatments else "approved range; no special treatment"


def _full_note(item: Mapping[str, Any], source_path: Path, treatment: str) -> str:
    parts = [
        f"Candidate C{int(item['candidate_id']):02d}",
        f"Treatment: {treatment}",
        f"Editorial intent: {item.get('rationale', '')}",
        f"Linked media: {source_path}",
    ]
    if item.get("source_start") is not None:
        parts.append(
            f"Source range: {float(item['source_start']):.3f}s–"
            f"{float(item['source_start']) + float(item['source_duration']):.3f}s"
        )
    if item.get("original_note"):
        parts.append(f"Owner note: {item['original_note']}")
    if item.get("owner_comment"):
        parts.append(f"Owner note: {item['owner_comment']}")
    if item.get("hybrid_note"):
        parts.append(f"Focused note: {item['hybrid_note']}")
    if item.get("finish_note"):
        parts.append(f"Resolve finish: {item['finish_note']}")
    return " | ".join(parts)


def build_fcpxml(
    items: Sequence[Mapping[str, Any]],
    source_media: Mapping[int, SourceMedia],
    bird_master: SourceMedia,
    *,
    timeline_name: str = "Pyrenees Hybrid · 3m25s · Originals",
    expected_item_count: int = 30,
    timeline_width: int = 1_920,
    timeline_height: int = 1_080,
    event_name: str = "Pyrenees Hybrid Handoff",
    audio_candidate_ids: frozenset[int] = frozenset(),
    sequence_note: str | None = None,
) -> tuple[str, dict[str, Any]]:
    if len(items) != expected_item_count:
        raise ValueError(
            f"Expected {expected_item_count} timeline items, received {len(items)}."
        )
    candidate_ids = [int(item["candidate_id"]) for item in items]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("Hybrid candidate IDs must be unique.")
    missing = set(candidate_ids) - {78} - set(source_media)
    if missing:
        raise ValueError(f"Missing source media for candidates: {sorted(missing)}")

    root = ET.Element("fcpxml", {"version": "1.10"})
    resources = ET.SubElement(root, "resources")
    ET.SubElement(resources, "format", {
        "id": "r1",
        "name": (
            "FFVideoFormat4K2997"
            if (timeline_width, timeline_height) == (3_840, 2_160)
            else "FFVideoFormat1080p2997"
        ),
        "frameDuration": "1001/30000s",
        "width": str(timeline_width),
        "height": str(timeline_height),
        "fieldOrder": "progressive",
        "colorSpace": "1-1-1 (Rec. 709)",
    })
    ET.SubElement(resources, "format", {
        "id": "r2",
        "frameDuration": "1001/30000s",
        "width": "3840",
        "height": "2160",
        "fieldOrder": "progressive",
        "colorSpace": "1-1-1 (Rec. 709)",
    })
    ET.SubElement(resources, "format", {
        "id": "r3",
        "frameDuration": "1/25s",
        "width": "3840",
        "height": "2160",
        "fieldOrder": "progressive",
        "colorSpace": "1-1-1 (Rec. 709)",
    })
    ET.SubElement(resources, "format", {
        "id": "r4",
        "frameDuration": "1001/30000s",
        "width": "1920",
        "height": "1080",
        "fieldOrder": "progressive",
        "colorSpace": "1-1-1 (Rec. 709)",
    })

    assets: dict[int, str] = {}
    for index, candidate_id in enumerate(candidate_ids, start=10):
        media = bird_master if candidate_id == 78 else source_media[candidate_id]
        asset_id = f"r{index}"
        assets[candidate_id] = asset_id
        duration = quantized_time(media.duration, frame_duration(media.fps))
        has_audio = candidate_id in audio_candidate_ids
        asset_attributes = {
            "id": asset_id,
            "name": media.path.name,
            "start": "0s",
            "duration": fcpx_time(duration),
            "hasVideo": "1",
            "hasAudio": "1" if has_audio else "0",
            "format": _format_id(media),
            "videoSources": "1",
        }
        if has_audio:
            asset_attributes.update({
                "audioSources": "1",
                "audioChannels": "2",
                "audioRate": "48k",
            })
        asset = ET.SubElement(resources, "asset", asset_attributes)
        ET.SubElement(asset, "media-rep", {
            "kind": "original-media",
            "src": media.path.resolve(strict=True).as_uri(),
            "suggestedFilename": media.path.name,
        })

    library = ET.SubElement(root, "library", {"colorProcessing": "standard"})
    event = ET.SubElement(library, "event", {"name": event_name})
    project = ET.SubElement(event, "project", {"name": timeline_name})

    timeline_items: list[dict[str, Any]] = []
    clip_specs: list[dict[str, Any]] = []
    offset = Fraction(0)
    for position, item in enumerate(items, start=1):
        candidate_id = int(item["candidate_id"])
        media = bird_master if candidate_id == 78 else source_media[candidate_id]
        media_frame_duration = frame_duration(media.fps)
        if candidate_id == 78:
            source_start = Fraction(0)
            source_duration = quantized_time(media.duration, media_frame_duration)
            output_duration = source_duration
        else:
            source_start = quantized_time(float(item["source_start"]), media_frame_duration)
            source_duration = quantized_time(float(item["source_duration"]), media_frame_duration)
            output_duration = quantized_time(float(item["output_duration"]), TIMELINE_FRAME_DURATION)
        treatment = _treatment_summary(item)
        clip_name = (
            f"{position:02d}_C{candidate_id:02d}_EXTENDED_BIRD_MASTER"
            if candidate_id == 78
            else f"{position:02d}_C{candidate_id:02d}_{media.path.stem}"
        )
        clip_specs.append({
            "position": position,
            "item": item,
            "candidate_id": candidate_id,
            "media": media,
            "source_start": source_start,
            "source_duration": source_duration,
            "output_duration": output_duration,
            "offset": offset,
            "treatment": treatment,
            "clip_name": clip_name,
        })
        timeline_items.append({
            "position": position,
            "candidate_id": candidate_id,
            "clip_name": clip_name,
            "source_path": str(media.path),
            "source_start_seconds": round(float(source_start), 6),
            "source_duration_seconds": round(float(source_duration), 6),
            "timeline_offset_seconds": round(float(offset), 6),
            "timeline_duration_seconds": round(float(output_duration), 6),
            "treatment": treatment,
            "rationale": item.get("rationale", ""),
            "original_note": item.get("original_note", ""),
            "hybrid_note": item.get("hybrid_note", ""),
            "finish_note": item.get("finish_note", ""),
            "has_source_audio": candidate_id in audio_candidate_ids,
            "uses_generated_media": candidate_id == 78,
        })
        offset += output_duration

    sequence = ET.SubElement(project, "sequence", {
        "format": "r1",
        "duration": fcpx_time(offset),
        "tcStart": "0s",
        "tcFormat": "NDF",
        "audioLayout": "stereo",
        "audioRate": "48k",
    })
    ET.SubElement(sequence, "note").text = sequence_note or (
        "30-shot hybrid linked to the untouched 4K originals. Candidate C78 uses the separately "
        "preserved 1080p approved extended bird master; its 4K source remains the recovery reference."
    )
    spine = ET.SubElement(sequence, "spine")

    for spec in clip_specs:
        item = spec["item"]
        candidate_id = spec["candidate_id"]
        media = spec["media"]
        source_start = spec["source_start"]
        source_duration = spec["source_duration"]
        output_duration = spec["output_duration"]
        treatment = spec["treatment"]
        clip_attributes = {
            "name": spec["clip_name"],
            "ref": assets[candidate_id],
            "offset": fcpx_time(spec["offset"]),
            "start": fcpx_time(source_start),
            "duration": fcpx_time(output_duration),
            "format": _format_id(media),
            "videoRole": "video",
        }
        if candidate_id in audio_candidate_ids:
            clip_attributes["audioRole"] = "dialogue"
        clip = ET.SubElement(spine, "asset-clip", clip_attributes)
        ET.SubElement(clip, "note").text = _full_note(item, media.path, treatment)
        if abs(media.fps - 25.0) < 0.02:
            ET.SubElement(clip, "conform-rate", {
                "scaleEnabled": "0",
                "srcFrameRate": "25",
                "frameSampling": "nearest-neighbor",
            })
        rate = float(item.get("playback_rate", 1.0))
        if candidate_id != 78 and abs(rate - 1.0) > 0.001:
            time_map = ET.SubElement(clip, "timeMap", {
                "frameSampling": "optical-flow" if item.get("motion_interpolation") else "nearest-neighbor",
                "preservesPitch": "1" if candidate_id in audio_candidate_ids else "0",
            })
            ET.SubElement(time_map, "timept", {
                "time": "0s",
                "value": fcpx_time(source_start),
                "interp": "linear",
            })
            ET.SubElement(time_map, "timept", {
                "time": fcpx_time(output_duration),
                "value": fcpx_time(source_start + source_duration),
                "interp": "linear",
            })
        crop_scale = float(item.get("crop_scale", 1.0))
        if abs(crop_scale - 1.0) > 0.001:
            scale = 1.0 / crop_scale
            ET.SubElement(clip, "adjust-transform", {
                "scale": f"{scale:.4f} {scale:.4f}",
            })
        marker_value = (
            f"C{candidate_id:02d} · APPROVED BIRD MASTER"
            if candidate_id == 78
            else f"C{candidate_id:02d} · {treatment}"
        )
        ET.SubElement(clip, "marker", {
            "start": fcpx_time(source_start),
            "duration": "1001/30000s",
            "value": marker_value,
            "note": _full_note(item, media.path, treatment),
            "completed": "0" if (item.get("stabilize") or float(item.get("contrast", 1.0)) != 1.0) else "1",
        })

    ET.indent(root, space="  ")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + ET.tostring(
        root, encoding="unicode", short_empty_elements=True
    ) + "\n"
    handoff = {
        "timeline_name": timeline_name,
        "timeline_resolution": f"{timeline_width}x{timeline_height}",
        "timeline_frame_rate": "30000/1001 (29.97)",
        "timeline_duration_seconds": round(float(offset), 6),
        "item_count": len(timeline_items),
        "original_4k_item_count": sum(1 for item in timeline_items if not item["uses_generated_media"]),
        "bird_master_item_count": sum(1 for item in timeline_items if item["uses_generated_media"]),
        "source_audio_item_count": sum(1 for item in timeline_items if item["has_source_audio"]),
        "items": timeline_items,
    }
    return xml, handoff


def write_handoff(
    destination: Path,
    xml: str,
    manifest: Mapping[str, Any],
    *,
    stem: str = "Pyrenees-Hybrid-3m25s-Resolve",
) -> tuple[Path, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    xml_path = destination / f"{stem}.fcpxml"
    manifest_path = destination / f"{stem}.json"
    xml_path.write_text(xml, encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return xml_path, manifest_path
