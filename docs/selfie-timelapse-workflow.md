# Pyrenees Selfie Timelapse Workflow

This workflow turns the reviewed Pyrenees selfie set into a face-alignment pilot without changing the original photographs.

## What the pilot does

1. Reads the completed selfie review and likely-selfie inventory.
2. Orders all reviewed photos chronologically.
3. Records dimensions, EXIF orientation, file identity, decisions, comments, and SHA-256 checksums in a source manifest.
4. Selects 15 representative photos: all commented or non-Include items, framing extrema, and beginning/middle/end samples.
5. Uses Apple Vision locally to detect the face, eyes, landmark confidence, and face-capture quality.
6. Creates a square soft-lock proposal:
   - Fill the square when the eye midpoint can remain inside the allowed central zone without excessive zoom.
   - Use a blurred extension only when filling would make the face unreasonably large.
   - Route unreliable landmark detections to an explicit exception queue.
7. Produces before/after contact sheets and a machine-readable report.

No generative edits, sharpening, relighting, or final video encoding happen in this pilot.

## Requirements

- macOS with the Swift command-line tools and Apple Vision framework.
- Python 3.
- Pillow from `requirements-selfie-timelapse.txt`.

## Run the pilot

```sh
python3 -m pip install -r requirements-selfie-timelapse.txt
python3 -m pyrenees_selects.selfie_timelapse pilot
```

To preserve an earlier pilot, choose a new output directory:

```sh
python3 -m pyrenees_selects.selfie_timelapse pilot \
  --output "/Volumes/Untitled/Pyrenees Selfie Timelapse/analysis/alignment-pilot-v3"
```

## Outputs

- `source-manifest.json`: immutable source identity and editorial state.
- `pilot-report.json`: landmarks, confidence, transforms, alignment policy, and failures.
- `aligned/`: proposed square pilot frames.
- `overlays/`: original images with the detected face, eyes, and proposed crop.
- `contact-sheet-*.jpg`: side-by-side review sheets.

## Interpreting the overlays

- Red rectangle: Apple Vision face box.
- Green dots: detected eye centers.
- Cyan rectangle: square crop mapped back onto the original.
- Green cross in the proposal: final eye-midpoint anchor.
- `fill-first`: the source fills the square while the eyes remain in the safe central zone.
- `background-extension`: exact alignment is possible only by revealing extended background.

## Production gates

1. Approve landmark accuracy and the soft-lock framing.
2. Run landmarks and transforms for all 307 photos.
3. Render a diagnostic video with filenames and dates.
4. Cull or repair only the exceptions visible at playback speed.
5. Apply restrained exposure, sharpness, and optional generative repairs.
6. Render a clean master and delivery versions.

Enhancement is deliberately late in the process: processing a frame that will later be removed wastes time and can make editorial comparison less reliable.

## Render the complete diagnostic

After the pilot framing is approved, run the full batch with explicit technical exclusions:

```sh
python3 -m pyrenees_selects.selfie_timelapse full \
  --exclude "PXL_20240613_141354634.jpg"
```

The full command:

- preserves the completed review;
- records technical removals separately;
- checkpoints Apple Vision results in resumable batches;
- creates clean aligned square frames;
- creates labeled diagnostic frames;
- holds each photo for three frames at 24 fps;
- encodes and verifies the diagnostic MP4 with FFmpeg and FFprobe;
- writes a report mapping every video frame back to its untouched source.
