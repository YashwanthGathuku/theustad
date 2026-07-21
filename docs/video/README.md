# TheUstad video archive

## Current TheUstad artifact

The current Build Week render is the 70-second
[`theustad-build-week-demo.mp4`](theustad-build-week-demo.mp4). It is produced by
[`build_theustad_narrated_demo.ps1`](build_theustad_narrated_demo.ps1) from the
raw desktop capture and its scene markers. It writes the H.264/AAC MP4,
cue-matched English SRT, transcript, machine-readable probe, SHA-256 checksum,
and fixed inspection frames under
[`../evidence/theustad-1.0/video`](../evidence/theustad-1.0/video).

The narration explicitly separates the real Codex control and plugin run from
the deterministic scripted conftest-poisoning rehearsal. It states that
`FINAL VERIFIED` is a protected verifier result rather than a universal code
correctness claim, and identifies Codex and GPT-5.6 as the build tools.

Render after recording with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File docs/video/build_theustad_narrated_demo.ps1
```

The build enforces the marker order, keeps every cue inside the edited source, maps
one H.264 video stream and one AAC audio stream, rejects silent narration, and
records the final probe and digest. The published candidate's SHA-256 is
`D236FF13EF24A5F1F065F32D1E19158D59AE983C6F0D6C41F993081F62DC1A86`.

## Historical Gate recordings

The following immutable files, URLs, digests, captions, and honesty labels are
preserved as historical Gate evidence. They are not canonical TheUstad setup
instructions.

### Narrated live real-project comparison

[`gate-real-project-live-narrated.mp4`](gate-real-project-live-narrated.mp4)
is a 175-second, 1920x1080 H.264/AAC recording of authenticated Codex runs
against clean clones of pinned `pytest-dev/iniconfig`. It is not a reconstruction
of earlier console text.

Public YouTube video: https://youtu.be/cAaMzRLyqWQ

```text
SHA-256: AEBC3A31727C3942CCE85D2ED4FCCD5887FD191D51565AF9E0B6068BC806D266
```

Matching captions remain at
[`gate-real-project-live-narrated.en.srt`](gate-real-project-live-narrated.en.srt).
[`gate-real-project-live.mp4`](gate-real-project-live.mp4) remains the original
silent source capture. Its original digest and machine-readable probe remain in
[`../evidence/real_project_video`](../evidence/real_project_video/README.md).

The historical timeline records an ordinary Codex control, historical plugin
installation, a protected child run, `FINAL VERIFIED`, and audit validation.
It was executed in WSL 2 because native Windows historical coding runs failed
closed.

### Original deterministic recording

[`gate-v2-demo.mp4`](gate-v2-demo.mp4) is the original 1 minute 55 second Build
Week recording. It is a 1920x1080 H.264/AAC file:

```text
SHA-256: 93A28FE92FC4827E36F320AFDC72ED281D15AA03492189087F5BE0B0DA391B38
```

Judge-accessible historical upload: https://youtu.be/kGGdz649zCQ

This is a deterministic-fixture submission video. It states that the fake
agent makes the rehearsal deterministic while the edits, deleted test, pytest
executions, historical verdicts, and audit chain are real. It also identifies
the separate live Codex run and its independently verified chain root.

The original public upload remains available at https://youtu.be/njgvvLapxs0.

## Historical rebuild commands

The retained scripts reproduce the historical renders only:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File docs/video/build_live_narrated_demo.ps1
powershell -ExecutionPolicy Bypass -File docs/video/build_demo.ps1
```

Generated intermediate assets remain intentionally ignored under `docs/video/build/`.
