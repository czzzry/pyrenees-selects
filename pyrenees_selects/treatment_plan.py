from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TreatmentRecipe:
    candidate_id: int
    source_start: float
    source_duration: float
    playback_rate: float = 1.0
    stabilize: bool = False
    crop_scale: float = 1.0
    contrast: float = 1.0
    motion_interpolation: bool = False
    rationale: str = ""

    @property
    def output_duration(self) -> float:
        return self.source_duration / self.playback_rate

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"output_duration": self.output_duration}


# Exact first treated rough-cut recipe derived from the owner's completed
# two-minute storyboard review on 2026-07-22. Candidate 43 moves later so the
# two cloud shots no longer play consecutively. Candidate 74 uses its complete
# three-second source and conservative interpolation to reach five seconds.
TREATED_ROUGH_CUT: tuple[TreatmentRecipe, ...] = (
    TreatmentRecipe(5, 5.7, 6.3, playback_rate=0.9, stabilize=True, rationale="Slow and smooth the rushed ocean zoom-out."),
    TreatmentRecipe(9, 69.0, 10.0, rationale="Remove the final two seconds requested in the storyboard note."),
    TreatmentRecipe(12, 9.0, 6.0, rationale="Sustained valley movement with the human anchor."),
    TreatmentRecipe(21, 5.0, 4.0, rationale="Brief grounded-drone transition."),
    TreatmentRecipe(22, 10.0, 9.0, rationale="Cut the first two seconds and hold longer on the walk away."),
    TreatmentRecipe(29, 31.0, 6.0, stabilize=True, rationale="Smooth the person-on-path composition."),
    TreatmentRecipe(34, 7.0, 11.0, stabilize=True, rationale="Keep the full post-adjustment zoom-out to the cabin."),
    TreatmentRecipe(36, 10.0, 15.0, playback_rate=1.5, rationale="Preserve the favorite canopy reveal while compressing it to ten seconds."),
    TreatmentRecipe(39, 37.0, 8.0, stabilize=True, rationale="Use the smoothest moving section of the misty path."),
    TreatmentRecipe(40, 104.0, 6.0, rationale="Use the later, thicker cloud field."),
    TreatmentRecipe(45, 146.0, 9.0, playback_rate=0.9, stabilize=True, crop_scale=0.88, rationale="Smooth, gently linger, and crop toward the waterfall."),
    TreatmentRecipe(50, 70.0, 8.0, stabilize=True, rationale="Extend the final lake-and-mist beat by two seconds."),
    TreatmentRecipe(43, 4.0, 8.0, stabilize=True, contrast=1.05, rationale="Space the cloud shots apart and smooth the move into cloud."),
    TreatmentRecipe(56, 0.0, 8.0, stabilize=True, rationale="Hold the full-valley view two seconds longer and smooth the end."),
    TreatmentRecipe(61, 6.0, 8.0, rationale="Hold longer as the mountain tops arrive."),
    TreatmentRecipe(63, 225.0, 7.0, rationale="Use the later basin-and-mountain-top reveal."),
    TreatmentRecipe(64, 480.0, 36.0, playback_rate=5.0, rationale="Compress the complete alpine sweep more aggressively so the end does not linger."),
    TreatmentRecipe(66, 20.0, 8.0, stabilize=True, rationale="Extend the planned cut by two seconds while smoothing the movement."),
    TreatmentRecipe(74, 0.0, 3.0, playback_rate=0.6, motion_interpolation=True, rationale="Slow the complete three-second source to five seconds without inventing extra scene content."),
    TreatmentRecipe(79, 100.0, 6.0, rationale="End on the hillside-to-cloud-sea transition."),
)


# The longer cut keeps the completed North Star treatments and adds only the
# selected alternate material needed for geographic texture and breathing room.
# Candidate 78 is a separately rendered signature master, so its insertion is
# represented in LONG_ROUGH_CUT_ORDER but not as a simple TreatmentRecipe.
LONG_ROUGH_CUT_ADDITIONS: tuple[TreatmentRecipe, ...] = (
    TreatmentRecipe(8, 432.0, 5.0, rationale="Short abstract ocean breath before the final coastal reveal."),
    TreatmentRecipe(11, 160.0, 5.0, rationale="Calm early-ridge establishing shot."),
    TreatmentRecipe(15, 62.0, 5.0, rationale="Trim before the abrupt final camera movement."),
    TreatmentRecipe(19, 274.0, 6.0, stabilize=True, rationale="Use the later horizon movement and smooth the camera path."),
    TreatmentRecipe(37, 5.0, 6.0, stabilize=True, rationale="Personal point-of-view transition from selfie into the misty trail."),
    TreatmentRecipe(41, 4.0, 5.0, rationale="Brief clear ridge above the cloud field."),
    TreatmentRecipe(46, 6.6, 6.0, stabilize=True, rationale="Use the later lake reveal and smooth the movement."),
    TreatmentRecipe(52, 6.0, 5.0, stabilize=True, rationale="Smooth the human-scale zoom-out beside the lake."),
    TreatmentRecipe(57, 6.0, 6.0, stabilize=True, rationale="Use the later shoreline range where the person becomes visible."),
    TreatmentRecipe(72, 20.0, 5.0, rationale="Calm green-hillside bridge with human scale."),
    TreatmentRecipe(73, 18.0, 5.0, rationale="Lodge-and-road settlement marker before the final mountains."),
    TreatmentRecipe(75, 0.0, 3.0, rationale="Preserve the complete captured three-second mountain punctuation."),
    TreatmentRecipe(76, 82.0, 5.0, rationale="Brief forested-mountain movement before the signature bird encounter."),
)


# Two explicit refinements from the owner's completed 13-shot hybrid review.
# Every other selected addition reuses the exact treatment already seen in the
# longer rough cut.
HYBRID_COMMENT_TREATMENTS: tuple[TreatmentRecipe, ...] = (
    TreatmentRecipe(
        37, 5.0, 5.0, stabilize=True,
        rationale="Honor the hybrid note by trimming the stabilized personal trail transition to five seconds.",
    ),
    TreatmentRecipe(
        52, 6.0, 5.0, playback_rate=0.8, stabilize=True, motion_interpolation=True,
        rationale="Honor the hybrid note by smoothing and modestly slowing the lakeside zoom-out.",
    ),
)


LONG_ROUGH_CUT_ORDER: tuple[int, ...] = (
    5, 8, 9, 11, 12, 15, 19, 21, 22, 29, 34, 36, 37, 39,
    40, 45, 46, 50, 41, 52, 57, 43, 56, 61, 63, 64, 66, 72,
    73, 74, 75, 76, 78, 79,
)


_NORTH_STAR_BY_CANDIDATE = {recipe.candidate_id: recipe for recipe in TREATED_ROUGH_CUT}
_LONG_ADDITION_BY_CANDIDATE = {recipe.candidate_id: recipe for recipe in LONG_ROUGH_CUT_ADDITIONS}
TREATED_LONG_ROUGH_CUT: tuple[TreatmentRecipe, ...] = tuple(
    _LONG_ADDITION_BY_CANDIDATE[candidate_id]
    if candidate_id in _LONG_ADDITION_BY_CANDIDATE
    else _NORTH_STAR_BY_CANDIDATE[candidate_id]
    for candidate_id in LONG_ROUGH_CUT_ORDER
    if candidate_id != 78
)
