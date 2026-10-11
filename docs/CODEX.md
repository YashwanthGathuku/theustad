# Use TheUstad with the Codex CLI

There are two ways in. Pick one per working tree.

| | Wrapper mode | Hook mode |
|---|---|---|
| Command | `theustad.py --repo PATH --task FILE` | `install-hooks --agent codex`, then `enroll` |
| Who runs Codex | TheUstad starts and stops `codex exec` itself | You run `codex` as usual |
| Boundary | Highest: TheUstad owns the agent process | A guardrail: Codex has to invoke the hooks |

This guide covers hook mode. In hook mode TheUstad runs as two Codex hooks:

- **SessionStart** freezes the repository's protected tests and configuration
  outside the repository, and records which tests exist (the test census).
- **Stop** fires when Codex finishes a turn. TheUstad checks the protected
  files and runs your fixed verifier. If the work is not really done, it
  blocks the stop: Codex sends TheUstad's verdict to the model as the next
  prompt and keeps working. A deleted or edited protected test is restored
  first.

Hooks only act in repositories you **enroll**. Everywhere else they return
immediately. Hook mode is experimental. The adapter was built from payloads
recorded from codex-cli 0.162.1 and is tested against that binary (see
[Recorded behaviour](#recorded-behaviour)).

## 1. Install the hooks

```bash
git clone https://github.com/YashwanthGathuku/theustad.git ~/theustad
python3 ~/theustad/theustad.py install-hooks --agent codex
```

This adds two handlers to Codex's user hooks file, `~/.codex/hooks.json`, or
`$CODEX_HOME/hooks.json` if you set `CODEX_HOME`:

- It keeps every other hook in the file.
- It writes a backup and replaces the file atomically.
- It refuses to rewrite a file it cannot parse.
- It replaces any older TheUstad handler instead of adding a second one.

The handlers use the absolute path of the interpreter and of this clone. Keep
the clone where it is, or run `install-hooks --agent codex` again from the new
location. `uninstall-hooks --agent codex` removes only TheUstad's handlers.

## 2. Trust the hooks in Codex

**Codex does not run a new hook until you trust it, and an untrusted hook does
nothing at all.** Start `codex`, run `/hooks`, and trust the two TheUstad
hooks. Codex records your approval in its `config.toml`. If a hook later
changes, for example after a reinstall from another path, Codex asks again.

`status --repo PATH` tells you which state you are in:

- `CODEX_HOOKS installed`: installed and trusted
- `CODEX_HOOKS untrusted`: Codex will not run them yet, or they changed since
  you trusted them
- `CODEX_HOOKS disabled`: hooks are turned off in Codex's `config.toml`
- `CODEX_HOOKS stale`: a handler cannot start, or is not the command
  `install-hooks` writes
- `CODEX_HOOKS unsafe`: a handler runs TheUstad from inside that repository

Reading trust needs Python 3.11 or newer. On Python 3.10 `status` says the
trust is unknown; check `/hooks` in Codex instead.

## 3. Enroll a repository

From your own terminal, not through Codex:

```bash
python3 ~/theustad/theustad.py enroll --repo /path/to/project \
  --verifier "/path/to/project-venv/bin/python -m pytest -q" --calibrate
```

Enrollment and its options are the same as for Claude Code; see
[the Claude Code guide](CLAUDE_CODE.md#2-enroll-a-repository). Then start a new
Codex session in the repository.

## What a session looks like

| Codex's last message | Verifier | Result |
|---|---|---|
| Claims completion | passes, census intact | Stop allowed; `VERIFIED` in the audit chain |
| Claims completion | fails | Stop blocked; Codex gets the failing output as its next prompt |
| Anything | protected file changed | Stop blocked; file restored; `TAMPERED` |
| Blocked too often | | `RETRY_EXHAUSTED`; never reported as `VERIFIED` |

`verify-chain --repo PATH --vendor codex` checks a session's audit chain.

## Recorded behaviour

These were observed with codex-cli 0.162.1, driving `codex exec` against a
local stand-in for the model API. `tests/test_codex_live.py` repeats them when
`codex` is installed.

- Codex runs hooks from `$CODEX_HOME/hooks.json` through your login shell
  (`$SHELL -lc`), in the repository, with `CODEX_HOME` set.
- A Stop hook blocks with exit 2 **and a message on stderr**, or with
  `{"decision": "block", "reason": ...}` on stdout. Codex sends the message
  back to the model and fires Stop again with `stop_hook_active: true`.
- Exit 2 with **empty** stderr does not block, and neither does any other
  failure. TheUstad never blocks without a message.
- **Codex sets no limit on how often a Stop hook may send it back.** Claude
  Code stops after eight. Two things keep TheUstad from trapping Codex in a
  loop:
  - The installed command first checks that `theustad.py` still exists. A
    deleted clone otherwise makes Python exit 2 with an error on every stop,
    which Codex reads as a block. A test that removes this check sees Codex
    loop until it is killed.
  - If TheUstad itself faults on eight consecutive stops in one turn, it lets
    the stop through, marked `UNVERIFIED (RETRY_EXHAUSTED)`. Verdicts are
    already bounded by the policy's `--max-blocks`.

## Limits

- **Same-user boundary.** The policy and snapshots live outside the
  repository, but a process running as you can still edit them, and that
  includes Codex's `hooks.json` and `config.toml`.
- **A project's `.codex/hooks.json` is the agent's to edit.** TheUstad installs
  user-level hooks only. Use [the CI check](CI.md) as the backstop that does
  not depend on the session.
- **Hooks you have not trusted do nothing.** Check `status` after installing.
- **POSIX.** Hook mode is supported on Linux, macOS and WSL 2.
