# Design Lock

## Objective

Help the owner move from an overwhelming 192-minute drone archive to a coherent short-film draft through a calm, fast review session and a lightweight storyboard assembler.

## Approved Direction

- Product model: reusable folder-backed projects, optimized only for Pyrenees 2024 initially.
- Critical journey: scan, analyze, screen candidates, refine Keeps and Maybes with notes, assemble variants, export.
- Review model: one candidate at a time with Keep, Maybe, and Skip.
- Review hierarchy: playable low-resolution candidate; two context frames; concise rationale; optional story role; persistent actions; review-time estimate.
- Refinement hierarchy: preserved original decision; replayable prepared selection; plain-language note; optional source-time marker; previous and next actions.
- Assembly model: a guided one-shot-at-a-time review of the two-minute plan first, with a compact sequence strip, an explicit visible-now/planned-later treatment split, a separate autosaving comment, and clear shot actions; a treated rough cut and shorter/longer variants follow.
- Visual direction: editorial travel journal and photographic contact print.
- Output: lightweight preview plus non-destructive DaVinci Resolve handoff.

## Visual Language

- Warm paper canvas and near-black ink.
- Editorial serif display type paired with restrained system sans-serif text.
- Strong rules, generous whitespace, frame numbers, dates, and archival metadata.
- Real footage is the dominant visual material.
- Acid green appears only on the primary affirmative action or selected state.
- Motion is functional and restrained; reduced-motion preferences are honored.

## Rejected

- The legacy seven-tab control panel.
- Dark cinematic SaaS styling.
- Generic gradients, glowing AI motifs, and dashboard card grids.
- A contact sheet of competing candidates during rapid review.
- A miniature professional video editor.
- Hidden destructive exports or manual timestamp transcription.

## Required States

- Empty project and invalid folder.
- Scanning and analysis progress, including safe cancellation later.
- Ready to review.
- Candidate media loading or unavailable.
- Decision recorded and undo.
- Review complete.
- Refinement note saving, refinement progress, and refinement complete.
- Storyboard preparation estimate, progress, safe pause, and failure summary.
- Storyboard pending, additional-note saving, approved, removed, alternate preview, restored, and complete.
- Draft generation and empty-selection guidance.
- Export success and actionable failure.

## Responsive And Accessible Behavior

- Desktop is primary, but review remains usable on a narrow viewport.
- Keyboard shortcuts never intercept focused form controls.
- Visible focus, semantic controls, sufficient contrast, and text alternatives are required.
- The visual hierarchy must survive sub-480p media and imperfect thumbnails.

## First Vertical Slice

Create the Pyrenees project from the real folder, scan the top-level source media, persist metadata and candidate decisions, generate disposable low-resolution review assets without touching originals, and render the approved editorial screening screen with real footage.

The completed screening is now followed by a refinement slice that protects the original 27 Keeps and 25 Maybes and attaches locally autosaved text notes to those selections.

The completed refinement is followed by a Pyrenees-specific, note-informed two-minute storyboard. It protects all prior state, prepares changed ranges locally at 360p, shows the preserved owner note plus a separate editable comment beside each proposal, and labels treatments as planned rather than already rendered. The bird enhancement remains explicitly deferred.
