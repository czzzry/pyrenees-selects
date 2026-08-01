# Decision Log

## Clean-Slate Rebuild In The Existing Repository

Replace the legacy product code and stale documentation while preserving Git history, public-repository safeguards, the license, and the security policy. Do not keep a legacy-code folder.

## Pyrenees-First, Reusable By Construction

Use clean project and folder boundaries, but validate every capability and performance decision against the real Pyrenees 2024 archive. Reusability is not permission to build speculative features.

## Screening Room Over File Browser

Present one sustained candidate sequence at a time. The user decides Keep, Maybe, or Skip without first selecting among 79 source files.

## Preserve Screening Before Refinement

When the last candidate is decided, snapshot every original Keep, Maybe, and Skip outcome. The refinement queue is derived from the preserved Keeps and Maybes, so adding notes or later changing working state cannot silently erase the completed screening.

## Text Notes Over In-App Dictation

Revisit selected moments with a plain text box that autosaves locally. Accept natural editorial language and an optional source-time marker, but do not request microphone access or build a macOS Dictation integration. Interpreting a note against the footage is a later, explicitly evaluated capability.

## Storyboard Over Timeline

Stage 2 creates duration variants and exposes shot cards for reorder, replacement, locking, and removal. DaVinci Resolve remains the precision editor.

## Review The Two-Minute Backbone First

Seed the completed Pyrenees footage-and-note analysis as explicit source-range recommendations without altering screening outcomes or refinement notes. Prepare only changed 360p ranges, disclose the measured 20–30 minute local estimate, and review the 20-shot two-minute backbone before deriving the shorter and longer variants. Keep the bird request visible but deferred until its enhancement feasibility is scoped separately.

## Separate Visible Ranges From Planned Treatments

The storyboard review must say exactly what its media shows: proposed start and end points only. Speed, stabilization, smoothing, and crops remain planned until a later treated rough-cut render. “Approve” therefore becomes “Approve shot and planned edits.” Each storyboard row also owns a separate autosaving comment so new feedback cannot overwrite the preserved second-pass note.

## Render The Approved Non-Bird Treatment Recipe Locally

Translate the fully approved 20-shot storyboard and its comments into an explicit, reviewable treatment recipe. Keep candidate #78 deferred, space the two cloud shots apart, and slow candidate #74's complete three-second source to exactly five seconds with conservative motion interpolation rather than implying that more source footage exists. Render versioned 360p segments outside the repository, resume safely from completed segments, and concatenate them into a disposable silent rough cut. The first complete run took 9 minutes 4 seconds and produced a 152.2-second preview, so rented compute is unnecessary for this pass.

## Preserve Signature Moments Across Variants

Treat candidates #74 and #78 as signature moments that must remain easy to retrieve even when they are absent from a particular cut. Candidate #74 is the complete three-second mountain accent slowed to five seconds. Candidate #78 is the bird encounter: use the validated 00:59.2–01:01.736 interval, begin wide with the bird against mountain and cloud, stabilize the background roll, then ease into the faithful tracked close crop. The smooth local version belongs in the film; super-resolution or generative bird enhancement remains an optional, clearly labeled side experiment.

## Keep The Bird-Inclusive North Star Separate

Render candidate #78 from the empirically validated 00:59.2–01:01.736 interval as a 4.57-second faithful 1080p master, then insert its 360p review copy after candidate #74 and before candidate #79. Preserve the original 2:32.2 North Star byte-for-byte and write the bird-inclusive 2:36.76 cut as a separate export. This gives the signature bird moment a late-film peak without turning an optional experiment into the only surviving edit.

## Preserve Short And Extended Bird Treatments

When the owner requests more bird time, retain the 4.57-second continuous wide-to-close master and add a separate 7.97-second extended treatment. Use 00:55.5–00:58.9 for the stabilized cloud-backed flight, make a deliberate match cut over 00:58.9–00:59.2 during the camera move, then continue with the existing mountain-backed treatment. Insert the extended review copy into another separate 2:40.16 North Star; do not overwrite either earlier cut.

## Reuse The North Star For The Longer Cut

Build the longer version as a separate export rather than replacing the 2:40.16 North Star. Reuse its 20 locked non-bird treatments, add 13 selected alternate shots, space the repeated cloud material with water and human-scale beats, and place the 7.97-second extended bird immediately before candidate #79's cloud-sea ending. The result is a 34-shot, 3:47.16 silent 360p review cut. Its measured local render took 7 minutes 1 second, so rented compute is unnecessary for this stage.

## Review Only The Thirteen Long-Only Shots For The Hybrid

Keep the 2:40.16 North Star as the hybrid backbone and ask the owner to review only the 13 treatments unique to the 3:47.16 cut. Play the exact finished treated clip and offer Add to hybrid, Long version only, or Unsure. Persist those choices separately in `hybrid_reviews`; do not repurpose Keep/Maybe/Skip, refinement notes, or the approved two-minute storyboard. Preserve both completed cuts regardless of the hybrid choices.

## Build The Hybrid From The Owner's Focused Choices

Add #8, #11, #15, #19, #37, #52, #72, #75, and #76 to the 2:40.16 backbone in the established long-cut order. Keep #41, #46, #57, and #73 exclusive to the 3:47.16 version. Honor the focused comments by trimming #37 to exactly five seconds and stabilizing and slowing #52 to 80%, while retaining the extended bird immediately before #79. The resulting separate 30-shot hybrid is 3:25.44 and rendered locally in 5 minutes 15 seconds. Preserve every earlier cut and all review state.

## Editorial Contact-Print Direction

Use the approved warm-paper, black-rule, serif-headline, contact-print visual direction. Reserve the acid-green accent for decisive actions. Avoid dark SaaS dashboards, generic AI visuals, and dense technical control panels.

## Local-First Media Handling

Never modify originals. Use disposable sub-480p review media, sparse analysis, and durable cached metadata. Remote compute may receive low-resolution proxies only after explicit user action.

## Open Editorial Interchange

Persist source identity and exact source ranges independently of rendered clips. Use an open editorial representation and export a Resolve-compatible format rather than making rendered subclips the primary handoff.
