# Market and positioning review

Reviewed: 12 August 2026

## What Resolve already solves

DaVinci Resolve can edit a 100 GB archive on a modest computer. Archive size alone is not the limiting factor; codec complexity, resolution, effects, storage speed, memory, and GPU capability matter more. Resolve's Cut page imports folders, presents a Source Tape for visually scrubbing all clips, supports In/Out selection and trimming, and works on small screens. Blackmagic's Proxy Generator can create H.264, H.265, or ProRes proxies from watched folder trees and link them automatically to the originals.

Sources:

- [DaVinci Resolve Cut page](https://www.blackmagicdesign.com/products/davinciresolve/cut)
- [Blackmagic Proxy Generator](https://www.blackmagicdesign.com/products/davinciresolve/collaboration)
- [DaVinci Resolve 21 manual](https://www.blackmagicdesign.com/welcome/en/W-DRE-03)

This means Selects cannot honestly position itself as the only way to edit a large archive on weak hardware. Resolve is the stronger finishing tool and already has an effective proxy workflow.

## Existing adjacent and direct products

The market does contain close alternatives:

- [Kyno](https://www.lesspain.software/kyno/) browses local media, creates markers and subclips, retains metadata, transcodes footage, and sends metadata and subclips to Resolve.
- [Focus](https://use-focus.com/) describes itself as a local pre-edit intelligence layer. It searches local speech and visuals, verifies exact source-backed moments, assembles sequences, and exports a Resolve EDL.
- [Selects](https://pullselects.com/) is a separate closed-beta Mac product with the same product name. It offers non-destructive highlights, editable AI logging, multi-clip timelines, local proxies, and direct Resolve export, while charging for cloud analysis credits.
- Resolve itself overlaps with folder import, Source Tape review, exact ranges, metadata, timelines, proxies, and export.

There is therefore no defensible claim that no other product mimics this workflow. The exact `Selects` name is also a release risk and needs brand and legal clearance before public promotion.

## Where the proposed workflow stacks up

| Product | Strongest at | Where it is ahead | Opening for this project |
| --- | --- | --- | --- |
| **Kyno** | Professional media management and conversion | Format support, batch metadata, verified backup, transcoding, team storage, and mature NLE integration | A simpler goal-led film workflow rather than a broad media-management suite |
| **Focus** | Local semantic search across speech, faces, scenes, and visual details | Search/index quality, transcription, GPU acceleration, multiple editor exports, and a finished paid desktop product | Free/open operation, explicit final-duration and shot-rhythm brief, comments/audio intent, and approval-gated external agents |
| **Selects by Pull Selects** | Rich AI logging for professional editors | Shot metadata, transcription, translation, subtitles, camera formats, confidence scoring, and broad NLE handoff | Zero-upload analysis, no credits, open manifests, and a human-first rough-film brief rather than metadata-first logging |
| **This project** | Goal-directed screening and reversible editorial decisions | Full-source context, several ranges per source, Keep/Maybe/Skip, comments, alternates, immutable versions, open FCPXML/JSON, and optional LLM proposals | Must still implement and prove the generic overnight candidate engine, semantic retrieval, professional format coverage, and distribution quality |

The proposed three-screen flow—**Project brief → Overnight plan → Review proposed moments**—is clearest where competitors are least explicit: the user says how long the film should be, chooses a rough shot rhythm, and receives more options than the cut requires. That is a useful product thesis, not yet a proven technical advantage.

## Defensible position

The useful opportunity is narrower:

> A free, open, human-first screening room for people who find a professional NLE cognitively expensive during first-pass review.

Potential differentiation:

- an explicit project brief captures target duration, rough shot rhythm, final format, creative direction, and candidate breadth;
- an overnight plan explains processing time, disk use, privacy, recovery, and expected candidate count before work begins;
- full-source context remains one click away from every chosen range;
- Keep, Maybe, Skip, comments, story role, and audio intent are first-class editorial decisions;
- selected-but-unused moments remain visible alternates rather than disappearing;
- sequence changes are immutable versions;
- LLMs propose inspectable diffs and cannot silently alter a project;
- no footage upload, subscription, analysis credits, or proprietary project lock-in; and
- the handoff is an open manifest plus FCPXML linked to untouched originals.

That position is useful, but it must be validated against Focus, Kyno, Resolve, and the separate Selects product with a neutral-project usability test.
