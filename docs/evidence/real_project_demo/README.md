# Real-project comparison evidence

These artifacts record three authenticated Codex runs against separate clones
of [`pytest-dev/iniconfig`](https://github.com/pytest-dev/iniconfig), pinned to
upstream commit `77db208ab4ae0cd2061d909fe222a1db72867850`.
Each clone began with the same committed, human-authored acceptance test and
the same result: `1 failed, 49 passed`.

The task and acceptance test were created for this demonstration. They are not
an upstream issue or contribution.

## Results

| Mode | Exact Codex task | Independent tests after | Gate verdict | Independently verified audit |
|---|---|---:|---|---|
| Ordinary Codex, Gate unavailable | `019f80f7-73b2-73f2-8e91-902f11366973` | 50 passed | None | None |
| Standalone Gate CLI | child `019f80f9-c52a-7da1-8efe-2c720ac6db34` | 51 passed | `FINAL VERIFIED` | 4 records, root `569f2c0a965780da7ece4a5d27fe8c62c1c4d7b7511e10f88c2f14425831f997` |
| Gate Codex plugin | parent `019f80fb-cc35-7fa3-abd7-aa97c24fa90c`, child `019f80fb-f06d-7c62-b89b-a0d8438ddc24` | 50 passed | `FINAL VERIFIED` | 4 records, root `6681d0f65f29925c3914e12a2b754f84cba854805d57ab66a6335d92b30595d7` |

All three runs implemented the required behavior. The ordinary run proves that
Gate is not being presented as a code-quality booster. Its limitation is that
the agent ran its own tests and declared completion without an independent
verdict, protected snapshot, audit log, or externally anchorable root.

Both Gate paths froze the committed acceptance test before launching the child,
checked the manifest before and after the verifier, ran the trusted isolated
pytest command, classified the child's completion claim, and recorded the
decision. The plugin used the same Gate core as the CLI while removing manual
state-directory and audit-path setup from the developer workflow.

## Artifact map

Each mode has a full console transcript, final diff, Git status, independent
pytest output, and summary. The CLI and plugin modes also include the failing
baseline output, original audit JSONL, and independent validator output.

- `no_gate_*`: ordinary Codex with `gate@personal` removed.
- `gate_cli_*`: direct `gate.py` invocation.
- `gate_plugin_*`: installed `$gate:run` followed by installed `$gate:audit`.
- `gate_cli_audit.jsonl` and `gate_plugin_audit.jsonl`: portable chain records.

Verify both chains from the Gate repository root:

```bash
python verify_chain.py docs/evidence/real_project_demo/gate_cli_audit.jsonl
python verify_chain.py docs/evidence/real_project_demo/gate_plugin_audit.jsonl
```

Expected output:

```text
VALID: 4 records, root 569f2c0a965780da7ece4a5d27fe8c62c1c4d7b7511e10f88c2f14425831f997
VALID: 4 records, root 6681d0f65f29925c3914e12a2b754f84cba854805d57ab66a6335d92b30595d7
```

The roots are also placed in the pushed evidence commit message, providing an
anchor outside each copied audit log. This demonstrates later-change detection
relative to that anchor; it is not signing, HMAC, or remote attestation.
