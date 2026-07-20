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

`test_results.txt` records `111 passed, 3 skipped` on native Windows. The
skips are the POSIX process-group and symlink cases; native Windows is not a
supported Gate runtime. The GitHub Actions matrix runs the complete suite on
Linux with Python 3.10 and 3.13.

## Codex plugin

- Package validator: `plugin_validation.txt`
- Plugin-era full test transcript: `plugin_test_results.txt`
- Personal marketplace installation and installed-runtime checks:
  `plugin_install.txt`
- Fresh Codex `$gate:audit` invocation: `plugin_skill_audit.txt`
- Fresh Codex thread: `019f80bd-68ce-7452-b995-a3f708981852`
- Installed audit exit code: `0`
- Installed audit root:
  `200042504cd90869d2bc8edcd60278049e231ead88ae69a60919a64a335d4a20`

The plugin package is installed and discoverable on this workstation. Its
read-only audit skill was exercised through a fresh Codex task. A live
`$gate:run` is intentionally not claimed here: the workstation has no WSL
distribution, and Gate fails closed on unsupported native Windows process
termination semantics.
