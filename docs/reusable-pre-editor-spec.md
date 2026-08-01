# Reusable, LLM-Assisted Pre-Editor

## Product contract

The application turns one or more folders of original video into reviewed source
ranges, one or more ordered sequence versions, disposable previews, and an
editable Resolve handoff. Originals are always read-only.

The deterministic application owns media identity, exact ranges, persistence,
preview rendering, validation, versioning, and export. An LLM may inspect the
project context and propose changes, but it cannot silently mutate a selection
or sequence.

## Core journey

1. Create a project and choose one or more footage folders.
2. Preflight readable, broken, vertical, silent, and unsupported media.
3. Seed a starting range from the chosen typical clip length; optional local
   analysis may later propose more ranges without blocking on one bad source.
4. Review each suggestion beside the full original.
5. Adjust In and Out points, create additional selections from the same source,
   decide Keep/Maybe/Skip, and attach comments or timestamped markers.
6. Collect Keeps and Maybes into a reusable selection pool.
7. Create a sequence version manually or accept an assistant proposal.
8. Keep selected-but-unused moments as alternates rather than discarding them.
9. Render a preview and inspect the exact ranges and approved treatments.
10. Export the same sequence version to FCPXML and a portable JSON manifest.

## Required concepts

### Source

A stable identity for an original file. Moving or disconnecting a source marks
it offline; rescanning never deletes editorial state. A source can be relinked.

### Suggestion

A disposable, regenerable candidate window produced by local analysis or an
assistant. A suggestion is not an editorial decision.

### Selection

A durable user-approved or user-considered range of a source. One source may
have many selections. A selection owns its In/Out times, decision, comment,
story role, audio intent, and approved treatment parameters.

### Sequence version

An immutable ordered list of selection references. Reordering, replacing, or
removing a shot creates a new version. Whether a selection is valuable is
separate from whether a particular sequence uses it.

### Proposal

A structured set of suggested changes from a human or LLM. Proposals are
reviewed as a diff, previewed when they affect picture or sound, and explicitly
accepted or rejected before application.

## Defaults

- Users select folders rather than individual files.
- Folder scanning is recursive by default with an inclusion preview.
- Target duration is a planning target with a visible tolerance, not a hard cap.
- Suggested shot length defaults to four to eight seconds, but is not a rule.
- Selecting more footage than fits the target is expected.
- Unused selections remain in the project as alternates.
- Remote analysis is off by default.

## Assistant modes

1. **Manual:** every core workflow works without an LLM.
2. **External agent:** Codex, Claude, or another agent uses the documented CLI
   or local MCP interface. No in-app provider credential is required.
3. **Built-in assistant:** the user supplies a provider credential for one
   request. The app does not persist it, and every remote job discloses what
   metadata will leave the computer. Operating-system credential storage is a
   possible later convenience, not required for the local-first contract.

Assistant actions follow one rule:

```text
observe -> propose structured diff -> preview -> user approves -> apply
```

## Agent interface

The `selects` command provides stable human-readable output, `--json` output,
and non-zero failure codes. The initial interface covers doctor, project
creation, source scanning and relinking, selection listing and editing,
comments and markers, sequence proposals and immutable versions, and Resolve
export. Mutating assistant work enters the proposal queue before application.

## Acceptance test for reuse

A release is reusable only when an unrelated second project can be completed
without changing source code or touching SQLite manually. The test must include
multiple folders, a broken file, a subsecond file, vertical media, media without
audio, two selections from one source, corrected In/Out points, persisted
comments, an unused alternate, sequence reordering, preview generation, and an
FCPXML handoff whose ranges match the preview manifest.

## Pyrenees boundary

The Pyrenees edit plans, candidate-number recipes, wildlife experiments,
selfie-timelapse work, music mix, title sequence, and final Resolve corrections
are a case study. They remain recoverable and testable, but they are not loaded
automatically by the reusable product.
