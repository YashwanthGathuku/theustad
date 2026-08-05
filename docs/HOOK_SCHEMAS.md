# Hook schema evidence

Last checked against the official Claude Code hooks reference on 2026-08-04.
These are documentation-derived fixtures, not a claim that a local Claude Code
binary has been exercised.

Official source: <https://code.claude.com/docs/en/hooks>

## Claude `SessionStart`

Required by the adapter:

- `hook_event_name`: exact value `SessionStart`
- `session_id`: non-empty string
- `cwd`: existing directory
- `source`: non-empty string; documented values are `startup`, `resume`,
  `clear`, `compact`, and `fork`

Other common or optional fields are retained in the raw payload but do not
control enforcement. The baseline is created only if the session has no
existing binding. Every repeated `SessionStart`, including compaction, reuses
the original baseline.

Fixture: `tests/fixtures/hooks/claude/session_start.json`.

## Claude `Stop`

Required by the adapter:

- `hook_event_name`: exact value `Stop`
- `session_id`: non-empty string
- `cwd`: existing directory (informational after session binding)
- `stop_hook_active`: boolean
- `last_assistant_message`: string, empty allowed

The official docs say `last_assistant_message` contains the final response and
should be used instead of the asynchronously written transcript when the hook
needs the current turn. `transcript_path` may be present but does not control
verification. Non-empty documented `background_tasks` or `session_crons`
arrays return `BACKGROUND_ACTIVE` so the verifier does not race in-flight or
scheduled edits. These arrays are documented for Claude Code v2.1.145 or later.

Fixture: `tests/fixtures/hooks/claude/stop_claim.json`.

## Fail-closed parsing

`SubagentStop`, `StopFailure`, substring matches, missing identity fields,
unknown vendors, and a command/payload event mismatch are rejected. There is
no `parse_codex = parse_claude` alias: similar-looking vendor schemas are not
treated as interchangeable.

## Required live-capture promotion checkpoint

Before describing hook mode as tested with a Claude Code version:

1. record `claude --version`;
2. capture real `SessionStart` and `Stop` stdin JSON outside the target repo;
3. redact only secrets or private paths, preserving keys and value types;
4. add the captures as versioned fixtures;
5. run `python -m pytest tests/test_hookadapter.py tests/test_hook_e2e.py -q`;
6. record a real `TAMPERED -> VERIFIED` session and independently validate its
   emitted audit chain.
