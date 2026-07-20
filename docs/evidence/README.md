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
