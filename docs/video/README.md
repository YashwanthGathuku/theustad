# Gate v2 demo video

## Live real-project comparison

[`gate-real-project-live-narrated.mp4`](gate-real-project-live-narrated.mp4)
is the current submission recording. It combines the actual desktop capture of
authenticated Codex runs against two clean clones of the pinned
`pytest-dev/iniconfig` project with a voiceover and burned-in captions. It is
not a reconstruction of prior console text.

Public YouTube video: https://youtu.be/cAaMzRLyqWQ

The 175-second, 1920x1080 H.264/AAC file has SHA-256:

```text
AEBC3A31727C3942CCE85D2ED4FCCD5887FD191D51565AF9E0B6068BC806D266
```

Its matching sidecar captions are
[`gate-real-project-live-narrated.en.srt`](gate-real-project-live-narrated.en.srt).
Rebuild the narrated file from the preserved raw capture with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File docs/video/build_live_narrated_demo.ps1
```

[`gate-real-project-live.mp4`](gate-real-project-live.mp4) remains the
original silent desktop capture used as the source recording. Its original
digest and machine-readable probe are retained under
[`../evidence/real_project_video`](../evidence/real_project_video/README.md).

Timeline:

- `00:00` real project, pinned baseline, and task.
- `00:11` ordinary Codex starts with `gate@personal` removed.
- `01:06` control result: tests pass; no Gate verdict, log, or root.
- `01:17` plugin installation and `gate@personal` discovery.
- `01:26` `$gate:run` starts through a fresh Codex parent task.
- `02:29` `FINAL VERIFIED`, exact child, audit root, and independent validation.
- `02:42` before/after comparison and original CLI command.

The terminal runs over the Codex Desktop window to keep the developer context
visible. On this Windows host, the successful coding run executes in WSL 2
because native Windows Gate execution intentionally fails closed. Installation
and Codex UI instructions are in [`../PLUGIN_GUIDE.md`](../PLUGIN_GUIDE.md).

Exact recording outputs and the copied audit chain are under
[`../evidence/real_project_video`](../evidence/real_project_video/README.md).

To reproduce from fresh prepared clones:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File docs/video/record_live_comparison.ps1
```

The recording harness rejects dirty targets, missing output artifacts, a
nonzero Codex/Gate result, a failed audit validation, or an incomplete capture.

## Original deterministic recording

`gate-v2-demo.mp4` is the 1 minute 55 second Build Week demo. It is a
1920x1080 H.264/AAC file with SHA-256:

```text
93A28FE92FC4827E36F320AFDC72ED281D15AA03492189087F5BE0B0DA391B38
```

The judge-accessible YouTube upload is:
https://youtu.be/kGGdz649zCQ

This is the original deterministic-fixture submission video. It remains as the
repeatable adversarial proof; the live real-project recording above is the
developer adoption and before/after proof.

The video states that the fake agent makes the rehearsal deterministic while
the edits, deleted test, pytest executions, Gate verdicts, and audit chain are
real. It also identifies the separate live Codex run and its independently
verified chain root.

To rebuild the original narrated video on Windows with Python, Pillow, FFmpeg,
and SAPI available:

```powershell
powershell -ExecutionPolicy Bypass -File docs/video/build_demo.ps1
```

Generated slides, narration, and intermediate segments are written under
`docs/video/build/` and are intentionally ignored.
