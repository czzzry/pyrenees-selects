from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PhoneTreatment:
    candidate_id: int
    stabilize: bool = False
    crop_scale: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    motion_interpolation: bool = False
    rotate_counterclockwise: bool = False
    zoom_strength: float = 0.0
    zoom_center_x: float = 0.5
    zoom_center_y: float = 0.5
    audio_playback_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Mechanical treatments chosen after the owner reviewed all phone candidates
# and then approved the 20-shot storyboard. Source ranges and final durations
# remain database-driven so later review changes cannot be silently ignored.
PHONE_TREATMENTS: tuple[PhoneTreatment, ...] = (
    PhoneTreatment(82),
    PhoneTreatment(83),
    PhoneTreatment(85, contrast=1.02, saturation=1.04),
    PhoneTreatment(88),
    PhoneTreatment(92, stabilize=True),
    PhoneTreatment(94),
    PhoneTreatment(97, crop_scale=0.75, contrast=1.08, saturation=1.05),
    PhoneTreatment(98),
    PhoneTreatment(102, contrast=1.05, saturation=1.06, zoom_strength=0.60, zoom_center_y=0.32),
    PhoneTreatment(103),
    PhoneTreatment(106),
    PhoneTreatment(110),
    PhoneTreatment(111, contrast=1.12, saturation=1.20),
    PhoneTreatment(
        113,
        crop_scale=0.58,
        contrast=1.08,
        saturation=1.06,
        motion_interpolation=True,
    ),
    PhoneTreatment(116),
    PhoneTreatment(
        119,
        stabilize=True,
        crop_scale=0.65,
        contrast=1.08,
        saturation=1.06,
        motion_interpolation=True,
    ),
    PhoneTreatment(124),
    PhoneTreatment(130, rotate_counterclockwise=True),
    PhoneTreatment(134, crop_scale=0.82, contrast=1.06, saturation=1.06),
    # Keep the first six seconds of source sound at normal speed so the spoken
    # “cow traffic jam” line remains intelligible over the compressed picture.
    PhoneTreatment(138, crop_scale=0.90, contrast=1.06, saturation=1.06, audio_playback_rate=1.0),
)
