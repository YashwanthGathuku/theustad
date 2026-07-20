# Gate v2 demo video

`gate-v2-demo.mp4` is the 1 minute 53 second Build Week demo. It is a
1920x1080 H.264/AAC file with SHA-256:

```text
902F5B6214417D4B6506A62BC450846BD013B6BB71480D15EC0E818526CBEB72
```

The video states that the fake agent makes the rehearsal deterministic while
the edits, deleted test, pytest executions, Gate verdicts, and audit chain are
real. It also identifies the separate live Codex run and its independently
verified chain root.

To rebuild on Windows with Python, Pillow, FFmpeg, and SAPI available:

```powershell
powershell -ExecutionPolicy Bypass -File docs/video/build_demo.ps1
```

Generated slides, narration, and intermediate segments are written under
`docs/video/build/` and are intentionally ignored.
