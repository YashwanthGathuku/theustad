# TheUstad 1.0 video evidence

This directory is the output location for the narrated Build Week demo. The
render script consumes `docs/video/theustad-build-week-demo-raw.mp4` and its
scene marker file, then writes:

- `video_probe.json`: final `ffprobe` stream and format metadata.
- `video_sha256.txt`: SHA-256 digest of the final MP4.
- `inspection-005s.png`, `inspection-018s.png`, `inspection-038s.png`,
  `inspection-049s.png`, `inspection-056s.png`, and `inspection-067s.png`:
  fixed review frames across the final render.

The build requires a 1920x1080 H.264 video stream, an AAC audio stream, a
non-silent narration track, and a final duration no greater than 178 seconds.
The deterministic conftest-poisoning sequence is narrated as a scripted
adversarial rehearsal; the control and plugin runs are identified separately.

The current probe records a 70-second render with video and audio, and
`video_sha256.txt` anchors the exact publication candidate.
