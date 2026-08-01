from __future__ import annotations


DRONE_HYBRID_ORDER: tuple[int, ...] = (
    5, 8, 9, 11, 12, 15, 19, 21, 22, 29, 34, 36, 37, 39, 40,
    45, 50, 52, 43, 56, 61, 63, 64, 66, 72, 74, 75, 76, 78, 79,
)
PHONE_APPROVED_ORDER: tuple[int, ...] = (
    82, 83, 85, 88, 92, 94, 97, 98, 102, 103,
    106, 110, 111, 113, 116, 119, 124, 130, 134, 138,
)

# Preserve the owner's approved drone-hybrid sequence while inserting the
# approved phone moments according to their actual capture dates. Candidate 43
# intentionally remains after 52 because that was an earlier approved editorial
# move to separate similar cloud shots.
INTEGRATED_DRONE_PHONE_ORDER: tuple[tuple[str, int], ...] = (
    ("phone", 82),
    ("phone", 83),
    ("drone", 5),
    ("drone", 8),
    ("drone", 9),
    ("phone", 85),
    ("phone", 88),
    ("drone", 11),
    ("drone", 12),
    ("phone", 92),
    ("phone", 94),
    ("phone", 97),
    ("phone", 98),
    ("phone", 102),
    ("phone", 103),
    ("drone", 15),
    ("phone", 106),
    ("phone", 110),
    ("phone", 111),
    ("phone", 113),
    ("phone", 116),
    ("phone", 119),
    ("drone", 19),
    ("drone", 21),
    ("phone", 124),
    ("phone", 130),
    ("phone", 134),
    ("drone", 22),
    ("phone", 138),
    ("drone", 29),
    ("drone", 34),
    ("drone", 36),
    ("drone", 37),
    ("drone", 39),
    ("drone", 40),
    ("drone", 45),
    ("drone", 50),
    ("drone", 52),
    ("drone", 43),
    ("drone", 56),
    ("drone", 61),
    ("drone", 63),
    ("drone", 64),
    ("drone", 66),
    ("drone", 72),
    ("drone", 74),
    ("drone", 75),
    ("drone", 76),
    ("drone", 78),
    ("drone", 79),
)
