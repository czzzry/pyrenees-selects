# Decision Log

## Streamlit For Local UI

Streamlit keeps the MVP simple, local, and easy to run without a separate frontend/backend stack.

## ffmpeg For Video Processing

ffmpeg is reliable for clipping, scaling, color filters, crossfades, audio trimming, and final MP4 export.

## Local-First Default

Drone footage is private and large. Local processing avoids upload risk and cloud costs by default.

## Remote Compute Is Future Optional

Remote processing is represented as a package export only. No provider code is included yet.

## Local Music Library

Music selection uses local files and optional local metadata. This avoids scraping, copyright ambiguity, and external music APIs.

## DaVinci Handoff Over Full Automation

The app prioritizes discovery, review labels, and handoff files because human editing judgment still matters. It does not pretend automatic montage fully replaces the editor.
