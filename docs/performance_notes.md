# Performance Notes

Recent performance report evidence showed:

- Analyzing frames: about 50.6% of runtime.
- Rendering selected clips: about 34.9% of runtime.

Conclusion:

Optimize analysis and caching before renting compute. The current priority is to reduce repeated OpenCV work with `cache/analysis_cache/`, use Fast Preview mode for early triage, and only then consider remote execution if local processing remains too slow.

Rendering is the second major bottleneck. If export is slow, lower resolution, shorten clips, use fewer clips, or prefer hard cuts over crossfades.
