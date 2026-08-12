# Productization readiness

Target: a credible, project-neutral public alpha that an Intel Mac user can install, understand, test, and hand off to Resolve without assistance from the original author.

## What is already credible

- The reusable app accepts one or more recursively scanned footage folders.
- Originals remain untouched and can be relinked after a drive move.
- A source can own multiple exact ranges, comments, markers, decisions, story roles, and audio intentions.
- Selected ranges can be assembled into immutable sequence versions while unused choices remain alternates.
- Preview and FCPXML/JSON handoff code is covered by the test suite.
- The localhost server has bounded media routes, Host checks, content security policy, and no telemetry.
- Manual use does not require an LLM; assistant work enters a reviewable proposal queue.
- The production app now implements project brief → calculated overnight plan → durable run lifecycle → ranked human review, including full-source context, exact range adjustment, and comments.
- Generated candidates, assistant proposals, user selections, and frozen sequence versions are separate durable concepts.

## Release blockers

1. **Fresh outsider proof.** Complete the acceptance journey with an unrelated second project on a clean application-data directory and no source edits; record the comprehension measures in the acceptance contract.
2. **100 GB low-power proof.** The durable engine now processes one source at a time, persists stages, publishes candidates mid-run, estimates disk, and owns a bounded power assertion. Validate runtime, thermals, pause latency, and free-space behavior against a representative 100 GB HEVC archive before promoting performance claims.
3. **Public Mac artifact.** Build, sign, notarize, staple, and Gatekeeper-test the declared Intel-only app on a clean Mac. The repository generates its icon from the checked-in SVG.
4. **Release truth.** GitHub's newest release is v0.2.0 while the package has moved beyond it. Do not present the old download as the reusable product.
5. **CI promotion.** Confirm the updated dependency install and new real-media/durable-run suite are green on the repository's supported Python matrix.
6. **Name collision.** Another current Mac product is already called Selects and operates in the same category. Decide the public name before promotion.
7. **Resolve conformance proof.** Import the generated FCPXML into a clean Resolve project and compare at least three CFR ranges and one VFR range with the JSON manifest and preview.

## Professional quality gaps

### Onboarding and comprehension

- Validate the implemented sequential design—Project brief → Overnight plan → Review proposed moments—with first-time users.
- Validate the generated sample project with first-time users; it now teaches one undecided source while demonstrating comments and assembly on two completed ranges.
- Validate the new project-readiness screen and its proxy size estimate against several codecs.
- Verify that the contextual first-selection guide retires after success and remains understandable with keyboard-only navigation.
- Expand the current readable, vertical, silent, and error summary with direct per-issue remediation.
- Add a native **Reveal in Finder** action to the new Resolve next-steps panel.

### Reliability and recovery

- Add a user-readable local diagnostics log with a deliberate copy/export action; run stages and user-readable failures are already persisted.
- Add backup restoration in the UI, not only backup creation.
- Test read-only folders and application upgrades; interrupted media work, partial artifacts, full disks, and restart recovery are covered by the current suite.

### Distribution and maintenance

- Publish a correctly versioned Intel Mac asset with checksums and release notes.
- Automate package installation and smoke tests in CI; add a macOS build job that at least produces and opens an unsigned test bundle.
- Keep the new changelog, contribution guide, issue templates, and documented support boundary current as behavior changes.
- Separate reusable product modules from legacy Pyrenees case-study modules, or rename the internal package so public stack traces no longer lead with `pyrenees_selects`.

### Product validation

- Observe at least three new users: a hobbyist, an experienced editor, and a low-power Intel Mac user.
- Measure time to first saved selection, completion of a first sequence, correction of an initially wrong range, and successful Resolve import.
- Compare the workflow directly with Resolve Source Tape, Kyno, Focus, and the other Selects product.

## Definition of done for the public alpha

- A new user follows one documented path from download to first exact selection in under ten minutes.
- The same user can complete a neutral project without changing code or opening SQLite.
- Large source review uses resumable proxies or clearly states that originals are being used.
- CI, install smoke tests, and browser acceptance tests pass on every supported platform.
- The signed release opens through Gatekeeper and contains licensed FFmpeg tools.
- Resolve imports the handoff with the same order, source ranges, orientation, and notes as the approved sequence.
- Known limitations, platform scope, privacy behavior, and support expectations are visible before download.
