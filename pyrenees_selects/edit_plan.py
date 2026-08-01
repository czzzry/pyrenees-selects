from __future__ import annotations

from typing import Any


# Editorial recommendations produced after the owner's completed second pass.
# These are source-time decisions; review proxies remain disposable.
EDIT_PLAN_ITEMS: dict[int, dict[str, Any]] = {
    3: {"recommendation": "drop", "start": 0.0, "duration": 4.4, "group": "ocean", "treatment": "Drop; candidates 5 and 9 are more dynamic ocean openings."},
    4: {"recommendation": "alternate", "start": 18.0, "duration": 8.0, "group": "ocean", "treatment": "Optional 10–15% crop to reduce the boats while retaining the person."},
    5: {"recommendation": "core", "start": 4.0, "duration": 8.0, "group": "ocean", "treatment": "Light stabilization; test 80–90% speed if the zoom-out feels rushed."},
    6: {"recommendation": "drop", "start": 0.0, "duration": 4.1, "group": "ocean", "treatment": "Drop; short source repeats the beach idea less effectively."},
    7: {"recommendation": "alternate", "start": 8.0, "duration": 8.0, "group": "ocean", "treatment": "Rotation is appealing, but removing boats requires a strong crop."},
    8: {"recommendation": "alternate", "start": 432.0, "duration": 8.0, "group": "ocean", "treatment": "Use as a short abstract ocean breath; surrounding footage has no stronger reveal."},
    9: {"recommendation": "core", "start": 69.0, "duration": 12.0, "group": "ocean", "treatment": "Use the later surf-to-beach reveal with people entering the composition."},
    11: {"recommendation": "alternate", "start": 160.0, "duration": 8.0, "group": "early-mountains", "treatment": "Calm ridge establishing shot."},
    12: {"recommendation": "core", "start": 8.0, "duration": 8.0, "group": "early-mountains", "treatment": "Keep sustained valley movement and the small human anchor."},
    13: {"recommendation": "alternate", "start": 14.0, "duration": 8.0, "group": "early-mountains", "treatment": "Good crag-to-valley movement; overlaps candidates 11 and 12."},
    14: {"recommendation": "drop", "start": 46.0, "duration": 8.0, "group": "early-mountains", "treatment": "Drop; less distinctive than neighboring mountain selections."},
    15: {"recommendation": "alternate", "start": 62.0, "duration": 6.0, "group": "early-mountains", "treatment": "Trim before the abrupt final movement."},
    16: {"recommendation": "drop", "start": 48.0, "duration": 8.0, "group": "early-mountains", "treatment": "Drop; weaker than later forest and cloud material."},
    18: {"recommendation": "alternate", "start": 126.0, "duration": 8.0, "group": "early-mountains", "treatment": "Road and pylons can serve as a travel transition, not a scenic hero shot."},
    19: {"recommendation": "alternate", "start": 268.0, "duration": 12.0, "group": "early-mountains", "treatment": "Use the later range where the mountain horizon arrives."},
    21: {"recommendation": "core", "start": 4.0, "duration": 6.0, "group": "human-journey", "treatment": "Brief self-aware grounded-drone transition."},
    22: {"recommendation": "core", "start": 8.0, "duration": 16.0, "group": "human-journey", "treatment": "Choose the cleanest 6–8 seconds as the person continues walking away."},
    23: {"recommendation": "alternate", "start": 24.0, "duration": 12.0, "group": "human-journey", "treatment": "Forest rotation continues but loses the human anchor."},
    27: {"recommendation": "drop", "start": 34.0, "duration": 8.0, "group": "paths", "treatment": "Drop; power lines and road repeat the travel beat less effectively."},
    28: {"recommendation": "alternate", "start": 20.0, "duration": 8.0, "group": "paths", "treatment": "Top crop can reduce settlement, but candidate 29 is cleaner."},
    29: {"recommendation": "core", "start": 30.0, "duration": 8.0, "group": "paths", "treatment": "Light stabilization; cleaner person-on-path composition than candidate 28."},
    34: {"recommendation": "core", "start": 7.0, "duration": 11.0, "group": "paths", "treatment": "Start after the leg adjustment; retain the zoom-out to the cabin and landscape."},
    36: {"recommendation": "core", "start": 10.0, "duration": 15.0, "group": "paths", "treatment": "Canopy-to-valley transition; test a gentle 125–150% speed-up."},
    37: {"recommendation": "alternate", "start": 5.0, "duration": 13.0, "group": "paths", "treatment": "Distinctive personal point-of-view transition from selfie to trail."},
    39: {"recommendation": "core", "start": 31.0, "duration": 17.0, "group": "paths", "treatment": "Remove idle beginning; stabilize and choose the smoothest misty-trail movement."},
    40: {"recommendation": "core", "start": 98.0, "duration": 12.0, "group": "clouds", "treatment": "Use the later range where the cloud field thickens."},
    41: {"recommendation": "alternate", "start": 4.0, "duration": 8.0, "group": "clouds", "treatment": "Clear above-cloud ridge; competes with candidates 40, 43, and 49."},
    43: {"recommendation": "core", "start": 4.0, "duration": 8.0, "group": "clouds", "treatment": "Let the natural move into cloud carry the effect; use restrained contrast only."},
    45: {"recommendation": "core", "start": 142.0, "duration": 16.0, "group": "water", "treatment": "Continue toward the lake; optional 10–15% crop to emphasize the waterfall."},
    46: {"recommendation": "alternate", "start": 2.0, "duration": 12.6, "group": "water", "treatment": "The extended source reveals more lake and waterfall but overlaps candidates 45 and 47."},
    47: {"recommendation": "alternate", "start": 0.0, "duration": 2.2, "group": "water", "treatment": "Complete source is 2.2 seconds; use only as a deliberate short punctuation."},
    49: {"recommendation": "alternate", "start": 26.0, "duration": 8.0, "group": "clouds", "treatment": "Attractive cloud-wrapped peak, less distinctive than candidates 40 and 43."},
    50: {"recommendation": "core", "start": 62.0, "duration": 16.0, "group": "water", "treatment": "Use the later lake opening and mist; choose a smooth 6–8 second section."},
    51: {"recommendation": "alternate", "start": 0.0, "duration": 6.7, "group": "water", "treatment": "Short human-by-lake beat; candidate 52 has a cleaner zoom-out."},
    52: {"recommendation": "alternate", "start": 6.0, "duration": 8.0, "group": "water", "treatment": "Smooth the zoom-out; pair with candidate 51 only if the cuts connect naturally."},
    53: {"recommendation": "alternate", "start": 30.0, "duration": 8.0, "group": "human-journey", "treatment": "Wide green landscape with human scale for the longer cut."},
    56: {"recommendation": "core", "start": 0.0, "duration": 12.0, "group": "high-mountains", "treatment": "Starting earlier gives the strongest full-valley view."},
    57: {"recommendation": "alternate", "start": 0.0, "duration": 12.0, "group": "water", "treatment": "No earlier footage exists; extension reveals the person along the shore."},
    58: {"recommendation": "drop", "start": 18.0, "duration": 8.0, "group": "water", "treatment": "Drop; redundant rocky shoreline without candidate 57's clearer payoff."},
    61: {"recommendation": "core", "start": 4.0, "duration": 8.0, "group": "high-mountains", "treatment": "Mountain hut is a useful human-built landmark and visual break."},
    63: {"recommendation": "core", "start": 220.0, "duration": 12.0, "group": "high-mountains", "treatment": "Use the later reveal where the mountain tops and basin arrive."},
    64: {"recommendation": "core", "start": 480.0, "duration": 36.0, "group": "high-mountains", "treatment": "Condense the slow-motion high-alpine sweep to roughly 8–10 seconds at 300–400%."},
    65: {"recommendation": "alternate", "start": 48.0, "duration": 6.0, "group": "high-mountains", "treatment": "Do not extend; trim before the abrupt downward pan."},
    66: {"recommendation": "core", "start": 20.0, "duration": 14.0, "group": "high-mountains", "treatment": "Choose the smoothest 6–8 seconds; trim or stabilize the fast final pan."},
    67: {"recommendation": "alternate", "start": 70.0, "duration": 8.0, "group": "high-mountains", "treatment": "Extension has no summit payoff; level and stabilize the original range."},
    72: {"recommendation": "alternate", "start": 20.0, "duration": 8.0, "group": "human-journey", "treatment": "Calmer green hillside bridge with human scale."},
    73: {"recommendation": "alternate", "start": 18.0, "duration": 8.0, "group": "human-journey", "treatment": "Lodge and road provide a settlement marker and visual variety."},
    74: {"recommendation": "core", "start": 0.0, "duration": 3.0, "group": "high-mountains", "treatment": "Signature moment — preserve the complete three-second source and slow it to five seconds with conservative motion interpolation."},
    75: {"recommendation": "alternate", "start": 0.0, "duration": 3.0, "group": "high-mountains", "treatment": "Complete source is three seconds; alternate punctuation for the longer cut."},
    76: {"recommendation": "alternate", "start": 82.0, "duration": 8.0, "group": "high-mountains", "treatment": "Pleasant forested mountain movement, less distinctive than candidates 66 or 74."},
    78: {"recommendation": "deferred", "start": 59.2, "duration": 2.536, "group": "bird", "treatment": "Signature moment — begin wide with the bird against mountain and cloud, stabilize the background, then use a smooth eased push into the faithful tracked close crop. Preserve an optional AI-enhancement experiment for later."},
    79: {"recommendation": "core", "start": 90.0, "duration": 16.0, "group": "ending", "treatment": "Use the transition from rotated hillside into the cloud-sea ending."},
}


STORYBOARD_VARIANTS: dict[int, list[tuple[int, float]]] = {
    90: [
        (5, 6), (9, 6), (12, 6), (22, 6), (34, 6),
        (39, 6), (40, 6), (43, 6), (45, 7), (50, 6),
        (63, 7), (64, 8), (66, 6), (74, 3), (79, 5),
    ],
    120: [
        (5, 6), (9, 7), (12, 6), (21, 4), (22, 7),
        (29, 6), (34, 7), (36, 7), (39, 7), (40, 6),
        (43, 6), (45, 8), (50, 6), (56, 6), (61, 6),
        (63, 7), (64, 8), (66, 6), (74, 3), (79, 6),
    ],
    180: [
        (5, 6), (8, 5), (9, 7), (11, 5), (12, 6), (15, 5),
        (19, 6), (21, 4), (22, 7), (29, 6), (34, 7), (36, 7),
        (37, 6), (39, 7), (40, 6), (41, 5), (43, 6), (45, 8),
        (46, 6), (50, 6), (52, 5), (57, 6), (56, 6), (61, 6),
        (63, 7), (64, 9), (66, 6), (72, 5), (73, 5), (74, 3),
        (75, 3), (76, 5), (79, 7),
    ],
}
