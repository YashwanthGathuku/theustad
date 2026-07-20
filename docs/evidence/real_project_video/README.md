# Live real-project video evidence

This directory preserves the exact outputs shown in
[`gate-real-project-live.mp4`](../../video/gate-real-project-live.mp4). The
recording is a real desktop capture of two authenticated Codex runs against
separate clean clones of `pytest-dev/iniconfig`, pinned to
`77db208ab4ae0cd2061d909fe222a1db72867850`.

The task and human-authored acceptance test are demonstration inputs, not an
upstream issue or contribution. Both clones began at `1 failed, 49 passed`.

## Recorded results

| Workflow | Exact task | Independent result | Gate evidence |
|---|---|---:|---|
| Ordinary Codex with Gate removed | `019f8114-db91-7e02-9be5-5ea375163ecc` | 51 passed | No verdict, log, or root |
| Installed Gate plugin | parent `019f8116-0610-7c70-8d50-7b532480af5d`, child `019f8116-30ab-7981-b85e-f45cbb74ceab` | 50 passed | `FINAL VERIFIED`; 4 valid records |

Recorded plugin audit root:

```text
5241d2d1e9ea87699c52333d7b8c16db8b6bbda961e9921c831992cb178c186b
```

Verify the copied chain from the repository root:

```bash
python verify_chain.py \
  docs/evidence/real_project_video/gate_plugin_audit.jsonl
```

Expected:

```text
VALID: 4 records, root 5241d2d1e9ea87699c52333d7b8c16db8b6bbda961e9921c831992cb178c186b
```

The audit root and video SHA-256 are placed in the pushed recording commit
message, anchoring both outside the copied audit and MP4.

## Video integrity

- Duration: 175 seconds (`00:02:55`).
- Frame: 1920x1080.
- Codec: H.264.
- Size: 6,473,336 bytes.
- SHA-256:
  `AC7240A101F72531E3CA69D6B601B5839C91318C1DC3D403660D229C23D26076`.

`video_probe.json` and `video_sha256.txt` preserve the machine-readable probe
and digest. The remaining files are the console transcripts, diffs, summaries,
test outputs, plugin listing, and original plugin audit chain captured by the
recording harness.
