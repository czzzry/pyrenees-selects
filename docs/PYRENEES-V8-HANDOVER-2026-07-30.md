# Pyrenees Extended Cut v8 — handover

Date: 30 July 2026

## Open this timeline

Project: **Pyrenees Integrated 4K**

Timeline: **Pyrenees Integrated Film · Extended Cut v8**

The previous **Extended Cut v7** timeline was left untouched as a fallback.

## Changes completed

### Opening restored

- Removed the later 10-second hyperlapse/full-train opening.
- Restored the approved pre-hyperlapse mountain-and-lake opening.
- Retained the moving title treatment.
- Title/subtitle: **PYRENEES / 2024 / THE EXTENDED CUT**.
- Restored the approved ocean-to-train opening sound.
- Opening duration is exactly 180 frames (6.006 seconds).
- Every later video layer, phone-audio moment, enhancement insert, and music cue was rippled together by 125 frames, so the edit remains synchronized.
- Cirrus now starts at frame 180, immediately after the restored opening.

### Waterfall restored from Pyrenees Hybrid

- Removed `Pyrenees-waterfall-slow-restored-v6.mp4`, the janky reconstruction.
- Rendered the waterfall directly from the protected timeline:
  - Project: **Pyrennes Hybrid**
  - Timeline: **Pyrenees Hybrid · Finishing v1**
  - Exact protected timeline range: frames 3090–3389
  - Exact source range: frames 4384–4655 of `DJI_20240702131315_0058_D.MP4`
- Placed the resulting exact 4K, 300-frame, 10.010-second Hybrid waterfall into v8.
- The replacement has normal framing: no added stretch, crop, rotation, or artificial zoom.

## Structural checks already passed

- Restored opening picture: frames 0–180.
- Restored opening sound: frames 0–180.
- First following shot begins at frame 180 with no opening gap.
- Music begins at frame 180 and ends at frame 9461.
- Exact Hybrid waterfall: frames 6390–6690.
- New timeline end: frame 9461.
- The protected v7 cat, ram, and cow corrections were carried forward.

## When reopening Resolve

1. Open **Pyrenees Integrated 4K**.
2. Select **Pyrenees Integrated Film · Extended Cut v8**.
3. Preview the first 10–15 seconds.
4. Preview the green marker named **Exact Hybrid waterfall**.
5. Continue reviewing v8; do not edit v7 unless deliberately reverting.

## Generated protected assets

- `/Users/cezarybaraniecki/Library/Application Support/Pyrenees Selects/revisions_v8/Pyrenees-approved-opening-v8-exact.mp4`
- `/Users/cezarybaraniecki/Library/Application Support/Pyrenees Selects/revisions_v8/Pyrenees-hybrid-waterfall-exact-v8.mp4`
- Opening audio reused from:
  `/Users/cezarybaraniecki/Library/Application Support/Pyrenees Selects/revisions_v5/Pyrenees-ocean-to-train-opening-v5.wav`

## Remaining work

- Human preview/approval of the restored opener and exact Hybrid waterfall.
- Resume the broader selected-clip comparison requested earlier after these two restorations are approved.
- Panorama reconstruction remains intentionally deferred.

## 31 July update — v9 six-clip viewing pass

New protected timeline:

**Pyrenees Integrated Film · Extended Cut v9 · Six Clip Preview**

This duplicates v8 and adds/replaces the following exact eight-second phone
ranges, without music finishing:

- C92 — `PXL_20240613_103400024.mp4`, 00:18–00:26
- C105 — `PXL_20240614_152820904.mp4`, 00:04–00:12
- C111 — `PXL_20240615_052909649.mp4`, 00:04–00:12, with a restrained rosy-morning grade
- C115 — `PXL_20240615_101435912.mp4`, 00:08–00:16
- C128 — `PXL_20240617_065921987.mp4`, 00:00–00:08
- C129 — the supplied `PXL_20240617_072939772.mp4` is genuinely only
  0.60 seconds long. The preview instead uses 00:05–00:13 of its 37.8-second
  continuation, `PXL_20240617_072941884.mp4`, which contains the requested
  look-down/map-to-mountains move.

Verification:

- 52 continuous V1 clips
- no V1 gaps or overlaps
- existing wildlife inserts and dialogue were moved with their pictures
- Cirrus deliberately remains unchanged at frames 180–9461
- new picture end is frame 10512, about 5 minutes 50.8 seconds
- v8 remains untouched

## 31 July update — v10 clean preview

New protected timeline:

**Pyrenees Integrated Film · Extended Cut v10 · Clean Preview**

This was regenerated from v9 and verified after three focused corrections:

- Removed the one-second enhanced sky-bird overlay on V2 without ripple. The
  underlying natural-speed shot remains; the ram insert is now the only V2 item.
- Replaced C129 with a metadata-safe horizontal render of 00:05–00:13 from
  `PXL_20240617_072941884.mp4`. It occupies the same frames as the prior C129
  item (4620–4861), so nothing later moved.
- Replaced the opening picture with a clean six-second master. It preserves the
  moving mountain/lake title and existing train imagery but contains no beach
  transition frames. Opening audio was not changed.

Authoritative v10 verification:

- 51 continuous V1 clips; no gaps or overlaps
- picture ends at frame 10392 (about 5:46.75)
- the existing two-piece Cirrus spine ends at frame 9341
- current music-free tail is 1051 frames / 35.07 seconds
- v8 and v9 remain untouched

Recommended later music pass (not yet implemented):

- use the original 350.72-second source track with an approximately four-second
  source offset (or trim/fade its final four seconds)
- keep it ducked under the six-second ocean/train opening
- fade it up around 00:06 and fade it out over the final 3–4 seconds
- the source track is about 3.97 seconds longer than the 346.75-second picture,
  so a short audio trim is enough; no picture trimming is required merely to
  make the music fit

## 31 July update — v11 audio and vertical polish

New protected timeline:

**Pyrenees Integrated Film · Extended Cut v11 · Audio + Vertical Polish**

The user ripple-deleted `21-phone-c116-v6.mp4` (the river/concrete-bridge
shot) from v10 before this pass. v11 preserves that deletion:

- 50 continuous V1 clips
- no picture gaps or overlaps
- picture/music end together at frame 10242 (about 5:41.74)

Audio:

- Replaced the obsolete, deeply ducked v6 music spine with the original Cirrus
  track, offset to fit the current picture and normalized to roughly -18 LUFS.
- Music is full by default.
- It stays low beneath the ocean/train opening.
- It dips only for the short spoken fragment in `07-phone`, the audible end of
  “it is cold,” the ram comment/call, the horse greeting and neigh, and the
  “cow traffic jam” phrase.
- Wind-only `02-phone` is not a duck trigger.
- The deleted `21-phone` background recording is neither restored nor used as
  a duck trigger.
- Horse and cow A1 items were corrected by one frame to align with picture.
- The new music fills the complete timeline and fades over its final 3.5 seconds.

Picture:

- C105 flower and C115 suspension-bridge portrait shots retain their complete
  upright composition. Black side pillars are replaced by a dark, softly
  blurred fill from the same frame.
- Cat, ram, and cow framing remains untouched.
- C111 morning shot has a somewhat warmer, rosier, more saturated grade with
  gentle added contrast while retaining highlight detail.

## 31 July update — v12 publish master

Final protected timeline:

**Pyrenees Integrated Film · Extended Cut v12 · Publish Master**

- Reverted the C105 flower and C115 suspension-bridge shots from blurred side
  fills to their original upright presentation with clean black pillars.
- Preserved the v11 dialogue-aware music mix, warmer C111 morning grade, and
  the user's ripple deletion of the river/concrete-bridge shot.
- Verified 50 continuous V1 clips, no gaps/overlaps, and picture/music ending
  together at frame 10242.

Validated YouTube master:

`/Users/cezarybaraniecki/Library/Application Support/Pyrenees Selects/exports/youtube/Pyrenees 2024 - The Extended Cut - 4K YouTube Master.mp4`

- 3840×2160, 30000/1001 fps
- H.264 High, 79.8 Mb/s, 10242 frames
- AAC-LC stereo, 48 kHz, 320 kb/s
- duration 341.824 seconds
- size 3,422,162,755 bytes

Prepared thumbnail:

`/Users/cezarybaraniecki/Library/Application Support/Pyrenees Selects/exports/youtube/Pyrenees 2024 - The Extended Cut - Thumbnail.jpg`

YouTube upload draft:

- Channel: Cezary Baraniecki
- Draft link: `https://youtu.be/WSvaynp2eg4`
- Upload began as Private
- Awaiting confirmation of title, description, audience, thumbnail, and final
  visibility before publication
