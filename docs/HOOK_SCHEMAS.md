# Hook schema evidence

Last checked against the official Claude Code hooks reference on 2026-08-04;
the hook `timeout` section below was checked on 2026-09-18.
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

The baseline covers both the protected-input manifest and, for a pytest
verifier, the test census, which is saved beside the manifest for `Stop` to
read. Re-baselining on re-entry would be an attack in itself: plant a
module-level skip, trigger a compaction, and the new baseline is the already
shrunken one.

That de-duplication is by `vendor + session_id`, which covers the
continuations that keep their id. A `resume`, `clear`, `compact` or `fork`
arriving with an id TheUstad has not bound is refused rather than baselined:
it would otherwise freeze the protected inputs as they stand after editing
and reset the retry counter, which SPEC 4.8a forbids. No new baseline is
written, `Stop` finds no binding and blocks through the path that already
exists for it, and the message says to restart Claude Code. Continuing such a
session properly would mean carrying its manifest, snapshots and counters
into the new session's state, which the manifest's recorded state directory
and snapshot paths do not allow to be copied; that is not attempted here.

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

## Hook `timeout` (emitted, not parsed)

This is the one field TheUstad *writes* into the host configuration rather than
reading from a payload.

- `timeout`: seconds, inside the command-hook object.
- Documented default for a `command` hook: 600.
- On reaching it the host cancels the hook, **discards its output**, and on
  most events renders no decision.

That last point is why the field matters: an omitted timeout leaves the host
default in force, and a verifier permitted to outlive the hook turns a blocking
verdict into a silent pass. `theustad.py enroll` therefore always emits an
explicit value and refuses any policy whose verifier deadline is not at least
`MIN_HOOK_MARGIN` seconds below it. See the hook-timeout section of the README.

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
