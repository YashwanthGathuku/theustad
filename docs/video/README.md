# Gate v2 demo video

`gate-v2-demo.mp4` is the 1 minute 55 second Build Week demo. It is a
1920x1080 H.264/AAC file with SHA-256:

```text
93A28FE92FC4827E36F320AFDC72ED281D15AA03492189087F5BE0B0DA391B38
```

The judge-accessible YouTube upload is:
https://youtu.be/kGGdz649zCQ

This is the original deterministic-fixture submission video. The replacement
real-project recording should follow [`../demo/README.md`](../demo/README.md),
using the pinned `pytest-dev/iniconfig` repository and the installed Codex
plugin. Keep this video and hash unchanged until the replacement has been run
on Linux, macOS, or WSL 2 and independently checked.

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
