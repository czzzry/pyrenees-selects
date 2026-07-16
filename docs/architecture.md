# Architecture

## Shape

Pyrenees Selects is a local-only web application with no account, remote service, or frontend build step.

- `pyrenees_selects/server.py`: localhost HTTP server and narrow JSON/media API.
- `pyrenees_selects/store.py`: SQLite schema and durable project, media, candidate, and decision state.
- `pyrenees_selects/media.py`: ffprobe metadata, source identity, and disposable 360p review assets.
- `pyrenees_selects/library.py`: top-level source scan and candidate creation policy.
- `pyrenees_selects/static/`: approved editorial screening interface.
- application data: stored outside both the repository and footage folder.

The server binds only to loopback and accepts localhost Host headers. It never serves arbitrary paths. Candidate media is validated against the configured top-level project folder before ffmpeg reads it.

## Media Contract

Original files are read-only inputs. A candidate stores:

- project and source-media identity;
- capture timestamp;
- source start and duration;
- source frame rate and dimensions;
- handle duration;
- chapter, rationale, score, decision, and optional story role.

The review proxy is not the edit decision. It can be deleted and regenerated from the source identity and range.

## Cache

Review clips and context frames live under the application data directory. Cache keys include the resolved source path, file size, nanosecond modification time, source range, asset kind, and rendering-policy version.

The initial review clip is H.264 at 360p with no audio. This keeps the 192-minute HEVC archive usable on the Intel Mac while retaining the original 4K media for Resolve.

## Current Vertical Slice

The first slice scans real metadata, persists a single sustained baseline candidate per source, lazily renders review assets, and records decisions. Baseline candidate placement is intentionally transparent and is not represented as intelligent highlight ranking.

The next engineering slice must replace baseline placement with sparse technical and visual analysis validated against a manually labeled Pyrenees subset. It should preserve the candidate and UI contracts rather than rewriting the product shell.

## Deferred

- Sparse scoring and cross-source novelty.
- Background job progress and cancellation.
- Guide-track analysis.
- Storyboard duration variants.
- OpenTimelineIO and Resolve export.
- Optional rented-compute packages.
- LightCut benchmark harness and audience evaluation.
