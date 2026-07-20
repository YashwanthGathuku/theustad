# Release evidence

This directory contains the permanent evidence used for the Gate v2 release.

## Deterministic rehearsal

- Console transcript: `rehearsal_console.txt`
- Audit chain: `audit_20260720_165329.jsonl`
- Verdicts: `FALSIFIED -> TAMPERED -> VERIFIED`
- Final exit code: `0`
- SHA-256 chain root:
  `200042504cd90869d2bc8edcd60278049e231ead88ae69a60919a64a335d4a20`

Verify the chain from the repository root:

```bash
python verify_chain.py docs/evidence/audit_20260720_165329.jsonl
```

## Live Codex run

- Audit chain: `live_audit_20260719_051748.jsonl`
- Exact Codex thread: `019f78cf-2302-7670-a725-6c89a41699c8`
- Verdicts: `INCOMPLETE -> TAMPERED -> VERIFIED`
- Final exit code: `0`
- SHA-256 chain root:
  `0faeacc75ff81ba953000d91fa94d74be195e12b2c42063ca9e9ed26019be8aa`

Verify the chain from the repository root:

```bash
python verify_chain.py docs/evidence/live_audit_20260719_051748.jsonl
```

## Test transcript

`test_results.txt` preserves the pre-plugin core run. The later
`plugin_test_results.txt` records `153 passed, 4 skipped` on native Windows and
`157 passed` on WSL 2. The Windows skips are POSIX process-group and symlink
cases; native Windows is not a supported Gate runtime. The GitHub Actions
matrix also runs the complete suite on Linux with Python 3.10 and 3.13.

## Codex plugin

- Package validator: `plugin_validation.txt`
- Plugin-era full test transcript: `plugin_test_results.txt`
- Version 0.2.0 native and WSL installation: `plugin_0_2_install.txt`
- Personal marketplace installation and installed-runtime checks:
  `plugin_install.txt`
- Fresh Codex `$gate:audit` invocation: `plugin_skill_audit.txt`
- Real-project recording preparation: `real_project_demo_prep.txt`
- Three-way real-project comparison: [`real_project_demo`](real_project_demo/README.md)
- Fresh Codex thread: `019f80bd-68ce-7452-b995-a3f708981852`
- Installed audit exit code: `0`
- Installed audit root:
  `200042504cd90869d2bc8edcd60278049e231ead88ae69a60919a64a335d4a20`

The plugin package is installed and discoverable. The earlier native-Windows
audit-only evidence remains for platform fail-closed coverage. The later WSL 2
comparison includes a live installed `$gate:run`, exact parent and child task
IDs, independent pytest output, installed `$gate:audit`, and a second direct
chain validation.

## Live real-project video

- Recording: [`../video/gate-real-project-live.mp4`](../video/gate-real-project-live.mp4)
- Exact outputs and audit: [`real_project_video`](real_project_video/README.md)
- Ordinary Codex task: `019f8114-db91-7e02-9be5-5ea375163ecc`
- Gate child task: `019f8116-30ab-7981-b85e-f45cbb74ceab`
- Gate verdict: `FINAL VERIFIED`
- Audit validation: `VALID: 4 records`
- Audit root:
  `5241d2d1e9ea87699c52333d7b8c16db8b6bbda961e9921c831992cb178c186b`
- Video SHA-256:
  `AC7240A101F72531E3CA69D6B601B5839C91318C1DC3D403660D229C23D26076`

The recording visibly compares a successful ordinary Codex result with the
same class of task through the installed plugin. Both produce working code;
only Gate produces the protected independent verdict and audit chain.
