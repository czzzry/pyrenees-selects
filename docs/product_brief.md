# Product Brief: Pyrenees Selects

## Outcome

Turn 79 DJI Mini 4 Pro videos from a 40-day Pyrenees crossing into a coherent short film without requiring the owner to watch the 3 hours and 12 minutes of source footage or manually create subclips.

The working duration hypothesis is two minutes. The product must also generate 90-second and three-minute alternatives so the eventual audience can evaluate duration rather than relying on a generic internet benchmark.

## Primary User And Dataset

The first customer is the footage owner. The first production dataset is authoritative:

- 79 top-level Pyrenees MP4 files totaling about 85 GB and 192 minutes.
- 30 top-level photographs.
- DJI Mini 4 Pro HEVC footage: mostly 4K/29.97 fps, with 4K/25 fps and 1080p exceptions.
- Capture dates from June 9 through July 19, 2024.
- A separate `canada/` folder plus panorama and hyperlapse source folders that are excluded from the first project.
- An Intel MacBook Pro with 16 GB memory and integrated graphics.

The architecture may support another folder-backed project, but no work should be spent on other cameras, genres, cloud accounts, teams, or hypothetical editing workflows until the Pyrenees dataset succeeds.

## Core Journey

1. Create or resume the Pyrenees project and choose the existing footage folder.
2. Scan originals without modifying or duplicating them.
3. Analyze sparse, sub-480p review media locally; optionally send only low-resolution proxies to rented compute later.
4. Review a condensed queue of sustained candidate sequences with Keep, Maybe, and Skip decisions.
5. Assemble kept sequences into 90-second, two-minute, and three-minute storyboard drafts.
6. Reorder, replace, remove, or lock shot cards without exposing a professional timeline.
7. Export exact source ranges and handles to DaVinci Resolve Free, plus a lightweight preview.

## Story Requirements

- The film should feel like a geographic journey without claiming strict chronology.
- The opening ocean is a required anchor when identified.
- The middle may reorder footage for pacing, variety, and visual continuity.
- The ending must create honest closure without fabricating an ocean shot.
- Most final shots should be sustained, initially targeting roughly four to eight seconds.
- Shots shorter than two seconds should occupy no more than five percent of the finished film.
- The system may ignore most sources; 79 files do not imply 79 cuts.
- Selections must retain their source file, frame-accurate range, frame rate, rationale, and two-to-three-second handles.

## Review Requirements

- The owner reviews condensed candidates rather than full sources.
- A target review budget is 15–20 active minutes; unattended processing is measured separately.
- Each review unit is a playable candidate sequence with two contextual frames from the same sequence.
- The interface explains why the candidate surfaced in plain language.
- Keep, Maybe, and Skip decisions persist and support keyboard shortcuts.
- Optional story-role labels include opening, transition, peak, and ending.

## Music Boundary

Music discovery, licensing, downloading, and audio production are excluded. Before final assembly, the user may provide one local guide track. A later assembly pass may use its duration and broad rhythmic structure for pacing.

## Benchmark

Compare the system with the free DJI LightCut product using the same representative input where practical. Record:

- elapsed processing time;
- active human time;
- disk use and financial cost;
- candidate acceptance rate;
- recall against a small manually labeled subset;
- technical defects and near-duplicate rate;
- shot-duration distribution;
- blind viewer completion, coherence, repetition, and preference measures.

## Non-Goals

- General-purpose AI video editing.
- A one-click final movie.
- A multitrack timeline or effects suite.
- Authentication, collaboration, or cloud media management.
- Support work for non-Pyrenees datasets before this one is successful.
- Destructive edits to source footage.
- Automatic music acquisition.

## Success

The project succeeds when the owner can process the real archive, review a useful condensed set of sustained moments, generate coherent duration variants, and open an editable Resolve timeline without manually finding or cutting the source ranges.
