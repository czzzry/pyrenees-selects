# Overnight product acceptance contract

This is the executable quality gate for turning the approved product flow into the real reusable application. A visual skin over the existing proxy workflow is a failure. Passing unit tests alone is insufficient.

## Golden visual references

Core journey:

1. [Project brief](assets/onboarding-prototypes/project-brief.png)
2. [Overnight plan](assets/onboarding-prototypes/overnight-plan.png)
3. [Review proposed moments](assets/onboarding-prototypes/review-samples.png)

Required adversarial-state references before the production UI slice can pass:

4. [Running](assets/onboarding-prototypes/overnight-running.png): current stage/file, completed/total, elapsed time, ETA provenance, safe stop, and completed samples available now.
5. [Paused](assets/onboarding-prototypes/overnight-paused.png): saved checkpoint, what is complete, resume and cancel actions.
6. [Completed with warnings](assets/onboarding-prototypes/overnight-attention.png): failed files, retry, skip, and review-ready output.
7. [Low disk](assets/onboarding-prototypes/overnight-low-disk.png): required space, available space, safety reserve, shortfall, alternate cache location, and return-to-manual-review action.
8. [Empty/unreadable folder](assets/onboarding-prototypes/empty-or-unreadable-folder.png): no valid sources, supported formats, choose-another-folder recovery, and retained project brief.

Production does not need demo content, but it must preserve the hierarchy, vocabulary, workflow order, visible trust guarantees, state coverage, and interaction density. Golden captures must omit prototype navigation overlays.

## Canonical project brief

All fields are persisted in SQLite, represented by the project API/CLI, editable after creation, included in the immutable run snapshot, and migration-tested.

| Field | Canonical values | New-project default | Engine effect |
| --- | --- | --- | --- |
| `target_duration_seconds` | integer 10–10,800 | 120 | Candidate-duration budget and assembly target |
| `shot_rhythm` | `energetic`, `balanced`, `observational`, `custom` | `balanced` | Candidate window lengths and expected count |
| `shot_min_seconds` / `shot_max_seconds` | 1–60; min ≤ max | 6 / 9 | Exact bounds for generated windows |
| `candidate_breadth` | `focused=1.25`, `generous=2.0`, `broad=3.0` | `generous` | Multiplier for candidate-duration budget |
| `orientation` | `landscape`, `portrait`, `undecided` | `landscape` | Preview/export format; not analysis rank |
| `intent` | plain text, ≤8,000 characters | empty | Human/assistant context only; the local heuristic must not claim to understand it |
| `audio_preference` | `speech_and_distinctive`, `visual`, `all` | `speech_and_distinctive` | Enables disclosed audio-activity weighting; it must not claim speech recognition |

Legacy `ideal_clip_duration` migrates to the closest rhythm and remains accepted by the CLI during one compatibility version. Existing projects with no target remain readable; starting a new analysis run requires choosing a target.

Behavioral tests prove that changing target duration, rhythm, breadth, and audio preference changes the plan or ranking exactly as documented. Orientation and intent tests prove persistence and downstream use without falsely affecting heuristic rank.

## Pure candidate planner

The planner is deterministic and independently testable.

- `readable_source_duration` is the sum of positive durations for unique sources currently in `ready` state. Offline, error, unsupported, and duplicate-fingerprint sources do not add budget.
- `candidate_duration_target = min(readable_source_duration, target_duration_seconds × breadth_multiplier)`.
- If `candidate_duration_target < shot_min_seconds` and the available sources are each at least `shot_min_seconds`, both count bounds are zero; the planner never fabricates an over-budget window.
- Otherwise, `minimum_candidate_count = ceil(candidate_duration_target / shot_max_seconds)` and `maximum_candidate_count = max(minimum_candidate_count, floor(candidate_duration_target / shot_min_seconds))`.
- Display exact integer bounds; do not cosmetically round the calculation.
- The planner never fragments a budget into sub-minimum windows across every file. When there are more eligible sources than the maximum proposal count, it chooses a deterministic spread across capture/path order, gives each chosen normal-length source one minimum-length opportunity, then distributes the remainder by unused duration. Manual full-source review continues to include every ready source.
- Candidate windows in one run do not overlap. Adjacent windows require at least one analysis sample interval between them.
- A source shorter than `shot_min_seconds`, including valid subsecond media, may yield one full-source proposal if analyzable.
- A source may yield zero, one, or several proposals. Quality thresholds may produce fewer than the planned range; status and UI explain the shortfall.
- If the entire candidate budget is shorter than the requested minimum shot length, normal-length sources yield no generated window rather than silently exceeding the budget. A genuinely shorter source may still yield its one full-source proposal.
- Candidate ordering is deterministic: descending score, then capture time, source relative path, and source In time.

Golden calculations:

| Target | Rhythm | Breadth | Readable footage | Candidate target | Expected count |
| --- | --- | --- | --- | --- | --- |
| 240 s | 6–9 s | 2× | ≥480 s | 480 s | 54–80 |
| 60 s | 3–5 s | 1.25× | ≥75 s | 75 s | 15–25 |
| 120 s | 10–16 s | 3× | 90 s | 90 s | 6–9 |
| 10 s | 6–9 s | 2× | 0.665 s | 0.665 s | one eligible full-source proposal |

## Candidate analysis oracle

The neutral FFmpeg-generated corpus includes known temporal phases, not merely arbitrary videos:

1. A 24-second landscape source: flat/dark 0–6 s, high-detail sustained motion 6–14 s, unstable flashes 14–20 s, flat 20–24 s. The top candidate must begin within ±one sample interval of 6 s and end within the selected rhythm bounds.
2. A 30-second landscape source with two separated high-detail movement phases. It must yield two non-overlapping proposals in temporal order when budget permits.
3. A source whose first half has active audio and second half is silent but visually equivalent. `speech_and_distinctive` may rank the active-audio window higher; `visual` must not use that weight. Rationale says `audio activity`, never `speech`, unless actual transcription is later implemented.
4. Portrait media with audio, landscape media without audio, a valid subsecond source, and a deliberately broken `.mp4`.

Every ranking rationale is assembled only from measured signals: exposure, visible detail, sustained movement, visual consistency, and disclosed audio activity. Production must not invent semantic titles, subjects, actions, locations, emotions, or speech content. Default labels are source filename plus source time range.

## Durable analysis-run model

Each run has an immutable `run_id`, algorithm version, project-brief snapshot, ordered source snapshot `(source_id, fingerprint, duration, media facts)`, creation time, and state.

Allowed run states:

```text
planned → running → completed
                  → completed_with_warnings
        → pausing → paused → running
        → cancelling → cancelled
        → failed
```

Each run-source row persists stage and state:

```text
pending → proxying → analyzing → rendering → completed
                                      ↘ failed
                                      ↘ skipped
                                      ↘ cancelled
```

Requirements:

- Run, source-stage, attempt count, failure, timestamps, progress totals, source fingerprint, and published artifact metadata are stored in SQLite—not only memory.
- Restart converts orphaned in-progress work to `paused`, retains failure explanations, validates completed artifacts, and resumes at the next safe source/stage boundary.
- Cancellation terminates the active FFmpeg process, removes `.partial` output, persists `cancelled`, and releases the power assertion within five seconds.
- Retry increments attempt count and retries only chosen failed/skipped work. A rerun creates a new run; old candidates remain associated with the old run.
- Changed project settings or source fingerprints make a prior plan `stale`; they never mutate its snapshot.
- Artifacts write to unique partial paths, pass ffprobe/duration validation, and publish by atomic rename. A nonempty file alone is not proof of completion.
- Completed candidates become reviewable while remaining run sources continue.

## Candidate, LLM proposal, and selection boundaries

- **Generated candidate:** regenerable measured source range belonging to one analysis run. It has rank, score components, rationale, artifact metadata, and review state `unreviewed`, `kept`, `maybe`, or `skipped`.
- **LLM proposal:** a pending structured project change in the existing approval queue. It is never called a generated candidate in code or UI.
- **Selection:** durable user-owned editorial range. Keeping or marking Maybe atomically records candidate review state and creates/updates a linked selection revision. Skipping does not create a selection.
- Regeneration never overwrites selections or their comments. A later run may link a near-identical candidate for context but cannot change the old review decision.

## Canonical timing and sample-media contract

- Canonical persisted time is integer microseconds, with inclusive In and exclusive Out.
- UI seconds are derived display values. API/JSON expose both integer microseconds and human-readable seconds during migration.
- CFR sources snap In down and Out up to source-frame boundaries. VFR sources retain microsecond PTS values and are labelled `VFR`; the app does not promise frame-index snapping without a frame map.
- End points clamp to source duration. A range must contain at least one frame/sample.
- Sample artifact: H.264/AAC review media representing exactly the candidate range, with source audio when present. Media time zero maps to `source_in_us`; manifest records source ID/fingerprint, source In/Out, output duration, codec and analysis version.
- Artifact duration tolerance is one source frame for CFR or 50 ms for VFR. Mismatches fail validation and are never published.
- `Open full source` loads the authorized original or full-source proxy and seeks to `source_in_us`. Adjusted In/Out persist after reload and export those same canonical timestamps.
- A burned-in frame/PTS fixture verifies the same inclusive first frame and exclusive end across candidate sample, full-source edit, low-resolution sequence preview, JSON manifest and FCPXML.

## Immutable sequence contract

A saved sequence version is a frozen editorial snapshot, not a list of mutable selection IDs. Each item snapshots source ID/fingerprint, canonical In/Out, order, comment, story role, audio intent, treatment and effective orientation. Later selection edits create a selection revision and a new sequence version. Tests prove v1 preview/JSON/FCPXML remain semantically identical after editing a selection and creating v2.

## Estimate, disk, and progress truth

- Disk estimate derives from ready-source duration, configured review bitrate, sample bitrate, and a documented container-overhead factor. The response exposes calculation inputs and `provenance=calculated`.
- Runtime initially displays `Estimating…` unless a benchmark exists. A rough fallback is labelled `conservative baseline`, never `measured on this Mac`.
- After one completed source, ETA derives from measured source-seconds processed per wall-second and carries `provenance=measured_this_run`. It updates only at source/stage checkpoints to avoid false precision.
- Source or setting changes recalculate the plan and mark old estimates stale.
- Required free space is `estimated_artifacts + max(2 GiB, 20% of estimated_artifacts)` safety reserve.
- Start is blocked when available space is below required space. UI shows available, estimated artifacts, safety reserve, shortfall, choose-cache-location, and manual-review recovery.
- `ENOSPC` removes partial output, pauses the run with a specific disk error, releases power assertion, and preserves completed work.
- Progress denominators are persisted stage tasks. Failures count as processed and appear as warnings; `completed_with_warnings` never looks indefinitely incomplete.

## Power assertion contract

- Sleep prevention is opt-in and only acquired when a run enters `running`.
- On macOS, the assertion process PID belongs to the run manager and is terminated on pause, cancel, completion, failure, server shutdown and handled exception.
- Restart never trusts a persisted PID. Resuming starts a new assertion.
- An unavailable assertion mechanism produces a visible warning and does not claim sleep prevention.
- Tests use a fake power provider to prove acquire/release lifecycle for success, pause, cancel, media failure, disk failure and application shutdown.

## Media and API authorization

- Server binds to loopback by default. Non-loopback binding requires an explicit unsafe development flag.
- Host must be loopback. `Origin`, when present, must equal the current loopback origin. State-changing requests with a foreign Origin are rejected.
- Source, full proxy, candidate sample, preview and export media resolve only through persisted IDs and the requested project/run/version relationship.
- Canonical paths must match the registered resolved source path or remain inside the configured cache/export root. Symlink escape and arbitrary path parameters are rejected.
- Source fingerprint is revalidated before proxy/sample render, sequence preview and export. A changed source marks artifacts stale and blocks output until rescan/relink confirmation.

## Resolve handoff integrity

- JSON and FCPXML identify project, frozen sequence version, source ID/fingerprint, canonical rational In/Out/duration, order, rotation/orientation and effective audio intent.
- FCPXML links to the revalidated untouched original, never review media.
- Preview and both manifests compile from the same frozen sequence snapshot.
- Audio intent is implemented or explicitly emitted as metadata/notes; the app must not claim destructive mute/mix behavior it does not perform.
- Three representative CFR ranges and one VFR range are compared after Resolve import before release promotion.

## Product journey

### Project brief

- First-time user selects one parent folder and understands nested folders are included.
- Target film duration and rough shot rhythm are explicit required inputs with useful defaults.
- The interface says they are planning targets, not hard deletion rules.
- Final format and optional creative direction remain visible.
- Candidate breadth and audio preference are advanced options.
- Expected duration/count is calculated from real inputs—no demo numbers.

### Overnight plan and lifecycle

- Preflight reports readable, duplicate, portrait, silent, VFR, very short, unsupported and broken sources.
- Plan explains enabled stages, estimate provenance, disk budget and expected output.
- User can start, safely pause, resume, cancel, retry/skip failures, choose another cache location, or bypass analysis for manual review.
- Running, paused, attention, low-disk and empty states match their visual references.

### Review proposed moments

- Ranked contact sheet shows source identity, canonical range, duration and measured rationale.
- User can play actual sample media, open the full source at the same timestamp and adjust the exact range.
- Keep/Maybe/Skip, comment, story role and source-audio intent persist after reload.
- One source can yield several selections and completed candidates are usable mid-run.
- Ranking is presented as a suggestion, never objective editorial truth.

### Assembly and handoff

- Target duration visibly reports over/under.
- Good candidates not used remain alternates.
- Reorder/replacement/edit creates a frozen new version.
- Preview, JSON and FCPXML agree and link to revalidated originals.

## Automated and human evidence

### Neutral corpus

The test fixture generates all media with FFmpeg and requires no Pyrenees paths. Original files are SHA-256 checksummed before and after every journey; any mutation is release-blocking.

### Automated

- Pure planner golden cases and schema/API validation for every brief field.
- Real-FFmpeg temporal oracle, multi-candidate, audio-weighting, broken-file, portrait, silent, VFR and subsecond tests.
- Durable state-machine tests for crash/restart, pause, cancel, retry, skip, partial failure, stale inputs, invalid artifact, low disk, ENOSPC and shutdown.
- Candidate-to-selection isolation and immutable sequence snapshot tests.
- Authorization tests for foreign Host/Origin, wrong project/run IDs, arbitrary path and symlink escape.
- Timing fixture compares sample, full-source edit, preview, JSON and FCPXML.
- Browser journey: brief → plan → start → progress → pause/resume → review completed sample → full source → adjust → comment/Keep → reload → assemble → export.
- Browser states at 1440×1050 and 500×900: no overflow or console errors, keyboard-only completion, logical focus, visible focus, 44px targets, WCAG AA contrast, reduced motion and meaningful status announcements.
- Validation/error screenshots and automated accessibility audit.
- Clean install, `selects doctor`, unit suite, JavaScript syntax, Python compilation, shell syntax and Intel app-bundle smoke.

### First-time comprehension

At least one person who did not build the app completes the neutral journey without coaching and can explain, in their own words: folder in → planning targets → overnight proposals → human verification → alternates/assembly → Resolve originals. Record errors, time to plan, time to first reviewed candidate and whether the user mistakes candidates for edits.

## Independent Sol judge gates

Three independent `gpt-5.6-sol` judges run at `xhigh` and do not edit while judging:

1. Product and visual fidelity.
2. Technical and data integrity.
3. Reliability and adversarial UX.

Each returns `PASS` or `BLOCK` with concrete evidence and blocking findings only. Any `BLOCK` triggers a bounded correction run, fresh verification and new independent judgment. Completion requires all three judges to pass the same candidate revision and all automated evidence to pass.

## Non-goals

- Replacing Resolve's timeline, color, sound, effects or delivery tools.
- Fabricated semantic understanding, titles, speech recognition or subject identification.
- Cloud upload, accounts, telemetry, subscriptions or credits.
- Apple-silicon or Windows packaging in this Intel-only slice.
- Renaming the product during this implementation; the public-name collision remains a separate release decision.
