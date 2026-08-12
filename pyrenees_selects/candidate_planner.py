from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


BREADTH_MULTIPLIERS = {"focused": 1.25, "generous": 2.0, "broad": 3.0}
RHYTHM_BOUNDS = {
    "energetic": (3.0, 5.0),
    "balanced": (6.0, 9.0),
    "observational": (10.0, 16.0),
}


@dataclass(frozen=True)
class PlannedSource:
    source_id: str
    fingerprint: str
    duration_seconds: float
    relative_path: str
    captured_at: str
    budget_seconds: float
    maximum_windows: int


@dataclass(frozen=True)
class CandidatePlan:
    readable_source_duration: float
    candidate_duration_target: float
    minimum_candidate_count: int
    maximum_candidate_count: int
    shot_min_seconds: float
    shot_max_seconds: float
    breadth_multiplier: float
    sources: tuple[PlannedSource, ...]
    duplicate_source_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "readable_source_duration": self.readable_source_duration,
            "candidate_duration_target": self.candidate_duration_target,
            "minimum_candidate_count": self.minimum_candidate_count,
            "maximum_candidate_count": self.maximum_candidate_count,
            "shot_min_seconds": self.shot_min_seconds,
            "shot_max_seconds": self.shot_max_seconds,
            "breadth_multiplier": self.breadth_multiplier,
            "sources": [source.__dict__ for source in self.sources],
            "duplicate_source_ids": list(self.duplicate_source_ids),
            "provenance": "calculated",
        }


def effective_bounds(brief: Mapping[str, Any]) -> tuple[float, float]:
    rhythm = str(brief.get("shot_rhythm") or "balanced")
    if rhythm in RHYTHM_BOUNDS:
        return RHYTHM_BOUNDS[rhythm]
    minimum = float(brief.get("shot_min_seconds") or 6)
    maximum = float(brief.get("shot_max_seconds") or 9)
    if not 1 <= minimum <= maximum <= 60:
        raise ValueError("Custom shot lengths must be between 1 and 60 seconds.")
    return minimum, maximum


def _unique_ready_sources(sources: Iterable[Mapping[str, Any]]) -> tuple[list[Mapping[str, Any]], list[str]]:
    unique: list[Mapping[str, Any]] = []
    duplicates: list[str] = []
    fingerprints: set[str] = set()
    for source in sources:
        if source.get("status") != "ready" or float(source.get("duration") or 0) <= 0:
            continue
        fingerprint = str(source.get("fingerprint") or source.get("id") or "")
        if fingerprint in fingerprints:
            duplicates.append(str(source["id"]))
            continue
        fingerprints.add(fingerprint)
        unique.append(source)
    return unique, duplicates


def build_candidate_plan(brief: Mapping[str, Any], sources: Iterable[Mapping[str, Any]]) -> CandidatePlan:
    target = brief.get("target_duration_seconds", brief.get("target_duration"))
    if target in {None, ""}:
        raise ValueError("Choose a target film duration before preparing candidates.")
    target_seconds = int(target)
    if not 10 <= target_seconds <= 10_800:
        raise ValueError("Target duration must be between 10 seconds and 3 hours.")
    minimum, maximum = effective_bounds(brief)
    breadth_name = str(brief.get("candidate_breadth") or "generous")
    try:
        multiplier = BREADTH_MULTIPLIERS[breadth_name]
    except KeyError as exc:
        raise ValueError("Candidate breadth must be focused, generous, or broad.") from exc

    unique, duplicates = _unique_ready_sources(sources)
    readable = sum(float(source["duration"]) for source in unique)
    candidate_target = min(readable, target_seconds * multiplier)
    if candidate_target <= 0:
        minimum_count = maximum_count = 0
    elif readable < minimum:
        minimum_count = maximum_count = 1
    elif candidate_target < minimum:
        minimum_count = maximum_count = 0
    else:
        minimum_count = math.ceil(candidate_target / maximum)
        maximum_count = max(minimum_count, math.floor(candidate_target / minimum))

    budgets = {str(source["id"]): 0.0 for source in unique}
    remaining = candidate_target
    eligible = [source for source in unique if float(source["duration"]) >= minimum]
    short = [source for source in unique if float(source["duration"]) < minimum]
    allocation_pool: list[Mapping[str, Any]] = []

    # A positive budget smaller than one minimum window still represents one
    # useful opportunity, not tiny fractions spread across every file. When
    # there is room, each normal-length source gets one opportunity before the
    # rest is distributed toward the longer sources.
    if eligible:
        ordered = sorted(
            eligible,
            key=lambda source: (
                str(source.get("captured_at") or ""),
                str(source.get("relative_path") or source.get("filename") or ""),
                str(source["id"]),
            ),
        )
        opportunity_count = min(len(ordered), math.floor(remaining / minimum)) if remaining > 0 else 0
        if opportunity_count == 0:
            allocation_pool = []
        elif opportunity_count == 1:
            allocation_pool = ordered[:1]
        elif opportunity_count == len(ordered):
            allocation_pool = ordered
        else:
            # Spread a bounded review budget across the capture order instead
            # of silently favoring only the longest or earliest files.
            allocation_pool = [
                ordered[round(index * (len(ordered) - 1) / (opportunity_count - 1))]
                for index in range(opportunity_count)
            ]
        for source in allocation_pool:
            allocation = min(minimum, remaining)
            budgets[str(source["id"])] = allocation
            remaining -= allocation
            if remaining <= 1e-6:
                break
    if not eligible and short and remaining > 0:
        allocation_pool = sorted(
            short,
            key=lambda source: (
                -float(source["duration"]),
                str(source.get("captured_at") or ""),
                str(source.get("relative_path") or source.get("filename") or ""),
                str(source["id"]),
            ),
        )[:maximum_count]
        for source in allocation_pool:
            allocation = min(float(source["duration"]), remaining)
            budgets[str(source["id"])] = allocation
            remaining -= allocation
            if remaining <= 1e-6:
                break

    while remaining > 1e-6:
        capacities = {
            str(source["id"]): max(0.0, float(source["duration"]) - budgets[str(source["id"])])
            for source in allocation_pool
        }
        capacity_total = sum(capacities.values())
        if capacity_total <= 1e-6:
            break
        distributed = 0.0
        for source in allocation_pool:
            source_id = str(source["id"])
            share = min(capacities[source_id], remaining * capacities[source_id] / capacity_total)
            budgets[source_id] += share
            distributed += share
        if distributed <= 1e-6:
            break
        remaining -= distributed

    planned_sources = tuple(
        PlannedSource(
            source_id=str(source["id"]),
            fingerprint=str(source.get("fingerprint") or ""),
            duration_seconds=float(source["duration"]),
            relative_path=str(source.get("relative_path") or source.get("filename") or ""),
            captured_at=str(source.get("captured_at") or ""),
            budget_seconds=round(budgets[str(source["id"])], 6),
            maximum_windows=(
                0
                if budgets[str(source["id"])] <= 0
                else 1
                if float(source["duration"]) < minimum or budgets[str(source["id"])] < minimum
                else math.floor(budgets[str(source["id"])] / minimum)
            ),
        )
        for source in unique
    )
    return CandidatePlan(
        readable_source_duration=round(readable, 6),
        candidate_duration_target=round(candidate_target, 6),
        minimum_candidate_count=minimum_count,
        maximum_candidate_count=maximum_count,
        shot_min_seconds=minimum,
        shot_max_seconds=maximum,
        breadth_multiplier=multiplier,
        sources=planned_sources,
        duplicate_source_ids=tuple(duplicates),
    )


def estimate_artifacts(plan: CandidatePlan, *, review_bitrate_bps: int = 1_520_000, sample_bitrate_bps: int = 1_120_000) -> dict[str, Any]:
    overhead = 1.08
    review_bytes = plan.readable_source_duration * review_bitrate_bps / 8
    sample_bytes = plan.candidate_duration_target * sample_bitrate_bps / 8
    estimated = math.ceil((review_bytes + sample_bytes) * overhead)
    reserve = max(2 * 1024**3, math.ceil(estimated * 0.20))
    return {
        "estimated_artifact_bytes": estimated,
        "safety_reserve_bytes": reserve,
        "required_free_bytes": estimated + reserve,
        "inputs": {
            "ready_source_seconds": plan.readable_source_duration,
            "candidate_seconds": plan.candidate_duration_target,
            "review_bitrate_bps": review_bitrate_bps,
            "sample_bitrate_bps": sample_bitrate_bps,
            "container_overhead_factor": overhead,
        },
        "provenance": "calculated",
    }
