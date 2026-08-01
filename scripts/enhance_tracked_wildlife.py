#!/usr/bin/env python3
"""Create a tracked, subject-enhanced wildlife shot for Resolve finishing."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [float(part) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be x,y,width,height")
    return tuple(parts)  # type: ignore[return-value]


def parse_size(value: str) -> tuple[int, int]:
    parts = value.lower().split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("size must be WIDTHxHEIGHT")
    width, height = (int(part) for part in parts)
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("size dimensions must be positive")
    return width, height


def clipped_square(
    frame: np.ndarray, center_x: float, center_y: float, size: int
) -> np.ndarray:
    height, width = frame.shape[:2]
    half = size // 2
    x0 = max(0, min(width - size, int(round(center_x)) - half))
    y0 = max(0, min(height - size, int(round(center_y)) - half))
    return frame[y0 : y0 + size, x0 : x0 + size]


def smooth(values: list[float], radius: int = 2) -> list[float]:
    result: list[float] = []
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        result.append(float(np.median(values[start:end])))
    return result


def track_boxes(
    frames: list[np.ndarray],
    anchor_index: int,
    anchor_bbox: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]:
    tracker_bbox = tuple(int(round(value)) for value in anchor_bbox)
    boxes: list[tuple[float, float, float, float] | None] = [None] * len(frames)
    boxes[anchor_index] = tuple(float(value) for value in tracker_bbox)

    tracker = cv2.TrackerCSRT_create()
    tracker.init(frames[anchor_index], tracker_bbox)
    last = boxes[anchor_index]
    for index in range(anchor_index + 1, len(frames)):
        ok, box = tracker.update(frames[index])
        if ok:
            last = tuple(float(value) for value in box)
        boxes[index] = last

    tracker = cv2.TrackerCSRT_create()
    tracker.init(frames[anchor_index], tracker_bbox)
    last = boxes[anchor_index]
    for index in range(anchor_index - 1, -1, -1):
        ok, box = tracker.update(frames[index])
        if ok:
            last = tuple(float(value) for value in box)
        boxes[index] = last

    return [box if box is not None else anchor_bbox for box in boxes]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--anchor-seconds", type=float, required=True)
    parser.add_argument("--bbox", type=parse_bbox, required=True)
    parser.add_argument("--subject-crop", type=int, default=240)
    parser.add_argument("--frame-crop-width", type=int, default=2160)
    parser.add_argument("--ai-input", type=int, default=320)
    parser.add_argument("--blend", type=float, default=0.92)
    parser.add_argument(
        "--tracking-size",
        type=parse_size,
        default=(540, 960),
        help="Tracking-frame size; choose one with the same aspect ratio as the source",
    )
    parser.add_argument(
        "--manual-centers",
        type=parse_bbox,
        help="Optional start_x,start_y,end_x,end_y path in the tracking frame",
    )
    parser.add_argument(
        "--realesrgan",
        type=Path,
        default=Path(
            "/tmp/realesrgan-ncnn-vulkan-20220424-macos/realesrgan-ncnn-vulkan"
        ),
    )
    args = parser.parse_args()

    capture = cv2.VideoCapture(str(args.input))
    source_fps = capture.get(cv2.CAP_PROP_FPS)
    source_width = int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
    source_height = int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    tracking_width, tracking_height = args.tracking_size
    start_frame = int(round(args.start * source_fps))
    step = max(1, int(round(source_fps / args.fps)))
    frame_count = int(round(args.duration * args.fps))

    tracking_frames: list[np.ndarray] = []
    source_indices: list[int] = []
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    decoded_index = start_frame
    while len(tracking_frames) < frame_count:
        ok, frame = capture.read()
        if not ok:
            break
        if (decoded_index - start_frame) % step == 0:
            tracking_frames.append(
                cv2.resize(
                    frame,
                    (tracking_width, tracking_height),
                    interpolation=cv2.INTER_AREA,
                )
            )
            source_indices.append(decoded_index)
        decoded_index += 1
    capture.release()
    if not tracking_frames:
        raise RuntimeError("No source frames decoded")

    anchor_index = min(
        len(tracking_frames) - 1,
        max(0, int(round((args.anchor_seconds - args.start) * args.fps))),
    )
    boxes = track_boxes(tracking_frames, anchor_index, args.bbox)
    if args.manual_centers:
        start_x, start_y, end_x, end_y = args.manual_centers
        centers_x = list(np.linspace(start_x, end_x, len(tracking_frames)))
        centers_y = list(np.linspace(start_y, end_y, len(tracking_frames)))
        _, _, box_width, box_height = args.bbox
        boxes = [
            (
                center_x - box_width / 2,
                center_y - box_height / 2,
                box_width,
                box_height,
            )
            for center_x, center_y in zip(centers_x, centers_y)
        ]
    else:
        centers_x = smooth([x + width / 2 for x, _, width, _ in boxes])
        centers_y = smooth([y + height / 2 for _, y, _, height in boxes])

    temp_root = Path(tempfile.mkdtemp(prefix="pyrenees-wildlife-"))
    subject_inputs = temp_root / "subject-inputs"
    subject_outputs = temp_root / "subject-outputs"
    subject_inputs.mkdir()
    subject_outputs.mkdir()

    for index, frame in enumerate(tracking_frames):
        crop = clipped_square(
            frame, centers_x[index], centers_y[index], args.subject_crop
        )
        crop = cv2.resize(
            crop, (args.ai_input, args.ai_input), interpolation=cv2.INTER_LANCZOS4
        )
        cv2.imwrite(str(subject_inputs / f"{index:04d}.png"), crop)

    subprocess.run(
        [
            str(args.realesrgan),
            "-i",
            str(subject_inputs),
            "-o",
            str(subject_outputs),
            "-m",
            str(args.realesrgan.parent / "models"),
            "-n",
            "realesr-animevideov3",
            "-s",
            "2",
            "-f",
            "png",
        ],
        check=True,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    encode = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            "3840x2160",
            "-r",
            str(args.fps),
            "-i",
            "-",
            "-an",
            "-c:v",
            "prores_ks",
            "-profile:v",
            "3",
            "-pix_fmt",
            "yuv422p10le",
            str(args.output),
        ],
        stdin=subprocess.PIPE,
    )
    assert encode.stdin is not None

    capture = cv2.VideoCapture(str(args.input))
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    track_to_source_x = source_width / tracking_width
    track_to_source_y = source_height / tracking_height
    track_to_source = (track_to_source_x + track_to_source_y) / 2.0
    crop_width = min(source_width, args.frame_crop_width)
    crop_height = int(round(crop_width * 9.0 / 16.0))
    crop_height -= crop_height % 2
    if crop_height > source_height:
        crop_height = source_height - source_height % 2
        crop_width = int(round(crop_height * 16.0 / 9.0))
        crop_width -= crop_width % 2
    source_to_output = 3840.0 / crop_width
    wanted_frames = {source_index: index for index, source_index in enumerate(source_indices)}
    decoded_index = start_frame
    written_frames = 0
    while written_frames < len(source_indices):
        ok, source = capture.read()
        if not ok:
            raise RuntimeError(f"Could not decode source frame {decoded_index}")
        if decoded_index not in wanted_frames:
            decoded_index += 1
            continue
        index = wanted_frames[decoded_index]

        center_x = centers_x[index] * track_to_source_x
        center_y = centers_y[index] * track_to_source_y
        crop_x = int(round(center_x - crop_width / 2))
        crop_x = max(0, min(source.shape[1] - crop_width, crop_x))
        crop_y = int(round(center_y - crop_height / 2))
        crop_y = max(0, min(source.shape[0] - crop_height, crop_y))
        background = source[
            crop_y : crop_y + crop_height, crop_x : crop_x + crop_width
        ]
        background = cv2.resize(
            background, (3840, 2160), interpolation=cv2.INTER_LANCZOS4
        )

        enhanced = cv2.imread(str(subject_outputs / f"{index:04d}.png"))
        patch_source_size = args.subject_crop * track_to_source
        patch_output_size = int(round(patch_source_size * source_to_output))
        enhanced = cv2.resize(
            enhanced,
            (patch_output_size, patch_output_size),
            interpolation=cv2.INTER_LANCZOS4,
        )

        patch_center_x = int(round((center_x - crop_x) * source_to_output))
        patch_center_y = int(round((center_y - crop_y) * source_to_output))
        x0 = patch_center_x - patch_output_size // 2
        y0 = patch_center_y - patch_output_size // 2
        x1 = x0 + patch_output_size
        y1 = y0 + patch_output_size

        if x0 >= 0 and y0 >= 0 and x1 <= 3840 and y1 <= 2160:
            _, _, box_width, box_height = boxes[index]
            mask = np.zeros((patch_output_size, patch_output_size), np.uint8)
            ellipse_width = int(
                box_width * track_to_source_x * source_to_output * 0.7
            )
            ellipse_height = int(
                box_height * track_to_source_y * source_to_output * 0.7
            )
            cv2.ellipse(
                mask,
                (patch_output_size // 2, patch_output_size // 2),
                (max(20, ellipse_width), max(20, ellipse_height)),
                0,
                0,
                360,
                255,
                -1,
            )
            mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=55, sigmaY=55)
            alpha = (
                mask.astype(np.float32)[:, :, None] / 255.0 * float(args.blend)
            )
            region = background[y0:y1, x0:x1].astype(np.float32)
            composited = enhanced.astype(np.float32) * alpha + region * (1.0 - alpha)
            background[y0:y1, x0:x1] = np.clip(composited, 0, 255).astype(np.uint8)

        encode.stdin.write(background.tobytes())
        written_frames += 1
        decoded_index += 1

    capture.release()
    encode.stdin.close()
    if encode.wait() != 0:
        raise RuntimeError("ffmpeg encoding failed")

    report = {
        "input": str(args.input),
        "output": str(args.output),
        "start_seconds": args.start,
        "duration_seconds": args.duration,
        "processing_fps": args.fps,
        "frame_count": len(source_indices),
        "anchor_seconds": args.anchor_seconds,
        "anchor_bbox_tracking_frame": args.bbox,
        "tracking_size": [tracking_width, tracking_height],
        "blend": args.blend,
        "frame_crop_width": crop_width,
        "manual_centers": args.manual_centers,
        "model": "realesr-animevideov3-x2",
        "resolution": "3840x2160",
        "temporary_working_directory": str(temp_root),
    }
    args.output.with_suffix(".json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    shutil.rmtree(temp_root)


if __name__ == "__main__":
    main()
