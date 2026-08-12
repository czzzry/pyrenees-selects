# Architecture

## Reusable product core

The public path is a local-only application with a stable command interface for humans and LLM agents:

- `preeditor.py` is the deep domain module. It owns projects, multiple footage roots, durable source identity, multiple selections per source, comments and markers, immutable sequence versions, alternates, and approval-gated proposals.
- `candidate_planner.py` is a pure deterministic planning module. It turns target duration, shot rhythm, candidate breadth, and unique readable source durations into exact candidate-budget and count bounds plus a documented disk estimate.
- `overnight.py` owns immutable run snapshots, persisted per-source stages, restart recovery, pause/cancel/retry/skip, power assertions, generated candidates, atomic candidate-to-selection review, and cache containment.
- `analysis.py` sparsely measures real temporal samples and can return multiple non-overlapping candidate windows per source. Its rationale vocabulary is limited to measured exposure, visible detail, movement, consistency, and audio activity.
- `preeditor_server.py` exposes a narrow loopback-only API and validates media against source records before serving it.
- `static/preeditor.*` implements the production brief → overnight plan → run lifecycle → human candidate review → assembly flow, plus manual source review and assistant proposal review, without a frontend build step.
- `review_proxies.py` owns deterministic, audio-preserving full-source review copies and a resumable background queue. A review copy is never used as the Resolve export source.
- `sequence_export.py` compiles the same sequence version into a disposable preview and a DaVinci Resolve FCPXML handoff linked to originals.
- `assistant.py` is an optional provider adapter. It sends a path-free project manifest—not media—to OpenAI and persists the answer only as a pending proposal.
- `cli.py` is the agent contract. Codex, Claude, or a script can inspect bounded context and create a proposal without editing SQLite directly.

Missing sources are marked offline rather than deleted, so ranges and comments survive a disconnected drive. Scanning continues after a broken file. Exported project manifests omit local paths and media bytes.

The older modules described below remain the Pyrenees case study and regression fixture. They are not the reusable domain boundary.

## Shape

The historical Pyrenees case-study application is a local-only web application with no account, remote service, or frontend build step.

- `pyrenees_selects/server.py`: localhost HTTP server and narrow JSON/media API.
- `pyrenees_selects/store.py`: SQLite schema and durable project, media, candidate, preserved screening, refinement-note, edit-plan, storyboard-review, and separate storyboard-comment state.
- `pyrenees_selects/edit_plan.py`: explicit Pyrenees source-range recommendations and 90-, 120-, and 180-second storyboard seeds.
- `pyrenees_selects/treatment_plan.py`: the approved non-bird rough-cut order and per-shot treatment recipe.
- `pyrenees_selects/media.py`: ffprobe metadata, source identity, disposable 360p review assets, treatment filters, and rough-cut concatenation.
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

Neither a full-source review copy nor a range preview is the edit decision. Both can be deleted and regenerated from the original and saved metadata.

## Cache

Review media lives under the application data directory. Cache keys include the resolved source path, file size, nanosecond modification time, source range, asset kind, and rendering-policy version. The reusable app can stream the untouched source on demand or prepare full-length, audio-preserving H.264 review copies in a resumable background queue. The source player lets the user switch between the review copy and original. Export always links back to the untouched original.

The Pyrenees case study also retains its older H.264 360p, silent range-preview cache. That specialized cache keeps the 192-minute HEVC archive usable on the Intel Mac while retaining the original 4K media for Resolve. Its unattended preparation is resumable at file boundaries, records progress outside the footage folder, and holds a macOS power assertion only while work is active.

## Current reusable vertical slice

The reusable path now persists a canonical project brief, calculates candidate duration/count and disk requirements, snapshots the brief and ordered source fingerprints into a run, and works one source at a time. Each source passes through proxying, sparse analysis, and exact sample rendering. A sample is published only after FFmpeg exits, ffprobe validates it, and a unique partial path is atomically renamed. Interrupted active work becomes paused on restart. A macOS sleep assertion exists only while a run is active.

Generated candidates, LLM proposals, and user selections are separate records. Keeping or marking Maybe creates a durable editorial selection; skipping does not. Candidate regeneration cannot overwrite comments. Sequence items freeze their source fingerprint, range, note, role, audio intent, and treatment, so later selection changes cannot rewrite an earlier preview or handoff.

Canonical candidate times are integer microseconds. CFR range edits snap outward to frame boundaries; VFR ranges retain microsecond timing and are labelled in the open handoff manifest. Preview and export revalidate the current original fingerprint and compile from the same frozen sequence snapshot.

## Pyrenees case-study vertical slice

The current slice scans real metadata, sparsely analyzes 160×90 frames with VideoToolbox acceleration on macOS, persists one scored sustained candidate per source, prepares review assets, and records decisions. First-pass screening includes an embedded full-source player with a jump-to-selection control and an autosaved comment. Once screening is complete, it snapshots the original outcome and exposes only Keeps and Maybes for a second pass. Refinement reuses the prepared 360p selection and carries the comment forward as an editable note with an optional source timestamp; it does not alter the source range or original decision.

For the completed Pyrenees review, an explicit edit-plan seed stores the note-informed recommendation, proposed source range, story group, and treatment separately from the protected screening and refinement tables. A resumable local job renders only changed two-minute ranges to a versioned 360p storyboard cache. These previews apply the range only, not the listed treatment. Storyboard rows persist pending, approved, removed, replacement, restored, and an additional autosaved comment that never overwrites the preserved refinement note. After all 20 rows are approved, a separate resumable renderer applies the locked non-bird treatment recipe to versioned per-shot outputs and concatenates a silent 360p rough cut. The bird candidate is represented but excluded from the storyboard and treated render until its separate feasibility decision.

The score combines exposure, visible detail, scenic movement, and within-shot continuity. It is an intentionally inspectable heuristic, not a semantic vision model. The Pyrenees edit plan was produced through dataset-specific footage and note review; automatic semantic plan generation is not claimed.

The first treated non-bird rough cut completed locally in 9 minutes 4 seconds and produced 20 validated H.264 segments plus a 152.2-second preview. Separate faithful bird treatments produced 2:36.76 and 2:40.16 bird-inclusive North Stars without overwriting that baseline. The longer-cut renderer then reused the 20 locked treatments, rendered 13 alternate segments, inserted the extended bird master, and assembled a validated 34-shot, 227.16-second preview in 7 minutes 1 second. The completed hybrid renderer filtered those additions through the owner's separate decisions, reused unchanged caches, rendered two comment-driven changes, and assembled a validated 30-shot, 205.44-second preview in 5 minutes 15 seconds. The next slice is owner review of that hybrid followed by a non-destructive Resolve handoff.

That comparison is a focused hybrid-review mode rather than another full-film pass. It filters the 180-second storyboard down to the 13 candidate IDs that appear only in the completed longer cut, serves their exact treated cache clips, and stores Add, Long only, or Unsure in `hybrid_reviews`. The original screening, refinement, 120-second storyboard, and rendered exports remain independent. Optional hybrid notes reuse only the corresponding 180-second storyboard row and never overwrite the second-pass note. `scripts/render_hybrid_rough_cut.py` refuses an incomplete focused review, keeps the 2:40.16 North Star as its backbone, restores only Add choices in long-cut order, inserts the extended bird master, and writes its export, cache, status, and manifest outside the repository.

## Deferred from the public v1

- Automatic semantic footage understanding. The local engine measures technical temporal signals; it does not identify subjects, transcribe speech, or understand creative direction. The optional assistant still reasons only over bounded project metadata and human decisions.
- Guide-track analysis.
- Owner review of the completed hybrid and any later 90-second derivation.
- OpenTimelineIO export (Resolve FCPXML is implemented).
- Optional generative bird enhancement beyond the completed faithful tracked treatments.
- Optional rented-compute packages.
- LightCut benchmark harness and audience evaluation.
