# Architecture

## Current Local Architecture

- `app.py`: Streamlit UI and current local orchestration.
- `processor.py`: future-facing job package/export utilities for local or remote workers.
- `diagnostics.py`: lightweight diagnostics/report access helpers.
- `music.py`: shared music constants/helpers.
- `ffmpeg`: video/audio trimming, color filters, montage assembly, and export.
- `OpenCV`: metadata fallback, thumbnail extraction, frame sampling, and segment scoring.
- `cache/analysis_cache/`: per-video cached analysis.
- `outputs/`: generated reports, clips, thumbnails, and exports.

## Future Remote Worker Concept

Remote execution is intentionally not implemented yet. The current app can export a remote job package containing config, manifest, environment notes, and setup instructions. A future worker could read that package, mount/copy the footage, run the same processor pipeline, and return outputs.

## Data And Privacy Notes

- Local Mac is the default backend.
- Remote processing may upload private footage to another machine.
- Raw footage, outputs, cache, and music library are excluded from Git.
- Music remains local to avoid API and copyright ambiguity.
- Remote compute should require explicit user action and provider-specific security review.
