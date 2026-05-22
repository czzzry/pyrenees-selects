# Product Brief

## Problem

Drone hiking footage creates a large review burden. The useful moments are often hidden inside long clips, and manual triage before editing in DaVinci Resolve takes time.

## Target User

Solo creators and small video teams who shoot outdoor drone footage and want a local-first assistant for rough cuts, clip discovery, and review handoff.

## Current MVP

- Local Streamlit UI.
- Folder-based footage selection.
- OpenCV frame analysis for motion, sharpness, stability, novelty, and rough moving-subject hints.
- Fast Preview and Final Quality render modes.
- Analysis caching for unchanged videos.
- ffmpeg rough-cut export.
- Clip Discovery labels and DaVinci review CSV/export support.
- Local music library selection without cloud APIs.

## Non-Goals

- No cloud upload by default.
- No paid APIs.
- No full replacement for human editing.
- No copyrighted music scraping.
- No provider-specific remote compute integration yet.

## Success Criteria

- The user can identify promising clips faster than manual scrubbing.
- Rough cuts export reliably on a local Mac.
- The app explains why clips were selected.
- DaVinci handoff files are useful for human review.
- Private footage stays local unless the user explicitly packages it for external compute.
