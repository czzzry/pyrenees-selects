# Changelog

All notable changes are recorded here. Selects follows semantic versioning while it remains an alpha; breaking behavior may still occur between minor versions and will be called out explicitly.

## 0.8.0 — 2026-08-12

- Implemented the project-neutral brief → overnight plan → durable run → ranked human-review workflow in the production app.
- Added deterministic candidate-budget/count planning, calculated disk gates, duplicate exclusion, and valid subsecond-source handling.
- Added resumable per-source proxying, multi-window sparse analysis, audio-activity weighting, exact sample rendering, pause/cancel/retry/skip, restart recovery, and bounded macOS sleep prevention.
- Added playable ranked proposals with full-source context, microsecond In/Out, CFR frame snapping, Keep/Maybe/Skip, comments, story roles, and source-audio intent.
- Frozen sequence items now preserve editorial ranges and notes after later selection edits; handoff manifests include source fingerprints and canonical timing.
- Added production running, paused, warning, low-disk, and empty-folder states plus their locked visual and executable acceptance artifacts.
- Clarified the project-neutral product position and current competitor landscape.
- Added a complete source-install and first-project guide.
- Declared test and desktop dependency groups in package metadata.
- Repaired the CI install order so optional case-study tests receive Pillow.
- Generated the generic Mac application icon from the checked-in SVG during builds.
- Added three reviewable onboarding prototypes and implemented the guided setup → readiness → first-selection flow.
- Added a generated local sample project that requires no personal footage or download.
- Added resumable full-source review copies with progress, disk estimates, source audio, and a one-click original toggle.
- Added project-neutral media inventory and explicit Resolve import steps after export.

## 0.7.0 — 2026-08-01

- Added reusable, folder-backed projects with recursive scanning.
- Added full-source review, multiple exact selections, comments, markers, and audio intent.
- Added immutable sequence versions, unused alternates, previews, and Resolve handoffs.
- Added manual, external-agent, and single-request built-in assistant modes.

## 0.2.0 — 2026-07-20

- Published the Pyrenees-specific local screening-room proof.
