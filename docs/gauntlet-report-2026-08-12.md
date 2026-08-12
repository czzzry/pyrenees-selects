# Productization gauntlet report · 2026-08-12

## Verdict

The repository now contains a **project-neutral, source-installable public alpha** for the complete folder → overnight proposals → human review → frozen sequence → Resolve handoff journey. The former product gap—the reusable overnight candidate engine—is implemented rather than represented by demo screens.

This is still an alpha, not a notarized consumer release. Human comprehension, a representative 100 GB run, Resolve import conformance, public naming, an Intel bundle smoke job in CI, and Developer ID/notarization remain release gates because they require people or environments outside this repository.

## What shipped

- A persisted project brief with target film duration, rough shot rhythm or custom range, proposal breadth, format, creative direction, and audio preference.
- A deterministic planner with exact candidate-duration/count math, unique-source accounting, calculated disk use, 2 GiB/20% reserve, and low-disk blocking.
- A durable per-source overnight pipeline: full-source review copy, sparse temporal measurement, several non-overlapping proposals, exact sample render, ffprobe validation, and atomic publication.
- Safe pause, resume, cancel, restart recovery, retry, skip, mid-run review, cache relocation, ENOSPC recovery, stale-input detection, and bounded sleep prevention.
- Honest ranking based only on measured exposure, detail, movement, consistency, and optional audio activity—no invented scene or speech understanding.
- Actual proposal playback beside the full source at the same timestamp, exact In/Out adjustment, Keep/Maybe/Skip, comments, story role, and source-audio intent.
- Separate durable concepts for generated candidates, approval-gated LLM proposals, user selections and their revisions, and immutable sequence versions.
- Frozen JSON/FCPXML exports linked to revalidated originals, with source IDs/fingerprints, integer-microsecond ranges, orientation/rotation, notes, and audio intent.
- A professional responsive interface for brief, plan, running, paused, warning, low-disk, empty-folder, review, manual sources, assembly, and assistant proposals.
- Project-neutral installation, onboarding, privacy/security, support, contribution, changelog, architecture, release, and troubleshooting documentation.

## Acceptance artifacts

The implementation was judged against the executable [overnight product acceptance contract](overnight-product-acceptance.md) and these locked visual references:

1. [Project brief](assets/onboarding-prototypes/project-brief.png)
2. [Overnight plan](assets/onboarding-prototypes/overnight-plan.png)
3. [Review proposed moments](assets/onboarding-prototypes/review-samples.png)
4. [Running preparation](assets/onboarding-prototypes/overnight-running.png)
5. [Paused preparation](assets/onboarding-prototypes/overnight-paused.png)
6. [Completed with warnings](assets/onboarding-prototypes/overnight-attention.png)
7. [Low disk](assets/onboarding-prototypes/overnight-low-disk.png)
8. [Empty or unreadable folder](assets/onboarding-prototypes/empty-or-unreadable-folder.png)

The goldens lock hierarchy, vocabulary, workflow order, visible trust guarantees and adversarial recovery states. Production uses real project/run data rather than the goldens' example numbers.

## Gauntlet evidence

The requested `gpt-5.6-sol` / `xhigh` independent-judge workflow ran directly because the optional `gnhf` executable is not installed in this environment. No claim is made that the unavailable CLI was used.

### Contract round

Three independent judges initially blocked vague planner math, timing, lifecycle, disk, source-integrity, accessibility and comprehension requirements. The contract and visual references were tightened, then all three judges passed the same corrected acceptance revision before implementation continued.

### Automated verification

- `106` project-neutral tests plus `5` generated timing cases passed with `ResourceWarning` promoted to an error.
- Real FFmpeg fixtures verify temporal ranking, multi-window selection, audio weighting, exact H.264/AAC sample duration, portrait/silent/subsecond/broken media, and original-file integrity.
- State tests verify success, pause, resume, cancel, crash recovery, media failure, disk failure, shutdown, power acquire/release, source changes, cache relocation and immutable review decisions.
- API tests verify canonical project fields, loopback Host/Origin policy, relationship-scoped media routes, source revalidation, frozen versions, JSON/FCPXML agreement, and historical-version stability.
- Migration tests exercise a real schema-v2 database and source file; frame-signature oracles prove samples and previews start at the requested source frame, not merely at a plausible duration.
- Python compilation, JavaScript syntax and shell syntax all passed.

### Installation and packaging

- A clean isolated virtual environment installed the current source package and passed `selects doctor` with writable app data plus FFmpeg/ffprobe discovery.
- The Intel-targeted `Selects.app` built at version `0.8.0`, passed strict ad-hoc code-signature verification, and produced a valid `Selects-0.8.0-macos-x86_64.zip` archive.
- Gatekeeper rejection is expected for an ad-hoc signature and remains explicit; Developer ID signing and notarization are not claimed.

### Production browser smoke

Two automated Playwright journeys passed against a neutral generated project. The actual application completed brief → calculated plan → live run → pause/resume → mid-run candidate review → full-source seek → exact range/comment/role/audio decision → reload → assembly → preview → protected Resolve export. The saved decision persisted. Desktop and narrow layouts had no horizontal overflow, review controls met the 44 px touch target, axe found no serious accessibility violations, the core editorial flow was keyboard-operable, and the browser console reported no errors or warnings.

## Independent implementation verdicts

Three independent `gpt-5.6-sol` judges at `xhigh` reasoning each reviewed the final candidate against a separate lens:

- **Product/UX contract: PASS** — the implemented journey and adversarial states match the locked artifacts.
- **Technical/media integrity: PASS** — deterministic planning, canonical timing, immutable versions, source revalidation, migration, export and local authorization evidence are coherent.
- **Reliability/recovery: PASS** — pause/resume/cancel, shutdown, sleep-lock lifecycle, disk exhaustion, retries, cache moves and artifact validation are covered.

Earlier judge blocks were treated as failures, corrected in code and tests, and resubmitted. The final verdicts above are from fresh re-reviews after those corrections.

## Remaining public-release gates

1. Observe an uncoached first-time user completing the neutral journey and record comprehension/time measures.
2. Run a representative 100 GB HEVC archive on the supported low-power Intel Mac and record runtime, thermals, pause latency, disk use and recovery.
3. Import three representative CFR ranges and one VFR range into Resolve and compare with the frozen JSON manifest and preview.
4. Choose and clear a public name; another adjacent Mac product already uses **Selects**.
5. Add an Intel macOS bundle-build/smoke job to CI; the full Python and real-browser suites are already required there.
6. Developer ID sign, notarize, staple, Gatekeeper-test and publish the version-matched archive with checksums.
7. Add diagnostics export, backup restore and Reveal in Finder as post-alpha recovery polish.
8. Separate or rename the historical `pyrenees_selects` internal package so public stack traces are fully neutral.

## Honest release decision

- **Ready now:** source installation, project-neutral alpha use, collaborator trials, local overnight preparation, human review and open Resolve handoff.
- **Built but not publicly distributable yet:** the ad-hoc-signed Intel `.app` archive.
- **Do not claim yet:** notarization, proven 100 GB performance, frame-perfect Resolve conformance, outsider comprehension, Apple-silicon packaging, semantic scene understanding, or a unique market category.
