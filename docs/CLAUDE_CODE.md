# Use TheUstad with Claude Code

In Claude Code, TheUstad runs as two lifecycle hooks:

- **SessionStart** freezes the repository's protected tests and configuration
  outside the repository, and records which tests exist (the test census).
- **Stop** fires when Claude tries to finish. TheUstad checks the protected
  files, runs your fixed verifier, and if the work is not really done it blocks
  the stop. Claude receives the evidence and keeps working. A deleted or
  edited protected test is restored first.

Hooks only act in repositories you **enroll**. Everywhere else they return
immediately. Hook mode is experimental: it follows Claude Code's documented
hook schema, but no recorded live session has certified a Claude Code version
yet.

## 1. Install the hooks (choose one)

### Option A: the Claude Code plugin

```bash
claude plugin marketplace add YashwanthGathuku/theustad
claude plugin install theustad@theustad
```

Inside Claude Code the same steps are `/plugin marketplace add
YashwanthGathuku/theustad` and `/plugin install theustad@theustad`. The plugin
tracks the repository; to stay on one reviewed commit, add the marketplace as
`YashwanthGathuku/theustad@<commit>`.

The plugin adds the two hooks and one read-only skill, `/theustad:status`.
Its hooks run `python3` from your `PATH`, which must be Python 3.10 or newer.

### Option B: settings hooks from a clone

```bash
git clone https://github.com/YashwanthGathuku/theustad.git ~/theustad
python3 ~/theustad/theustad.py install-hooks
```

`install-hooks` adds the two handlers to `~/.claude/settings.json` (or
`$CLAUDE_CONFIG_DIR/settings.json`):

- It keeps every other setting and hook.
- It writes a backup and replaces the file atomically.
- It refuses to rewrite a file it cannot parse.
- It replaces any older TheUstad handler instead of adding a second one.

`uninstall-hooks` removes only TheUstad's handlers. `--dry-run` prints the
result without writing it.

The handlers use the absolute path of the interpreter and of this clone, so
keep the clone where it is. If you move it, run `install-hooks` again from
the new location.

If both the plugin and settings hooks are installed, the plugin's copy stands
down and the settings hooks do the work, so one session is never verified
twice. It stands down only for the settings hooks `install-hooks` writes,
when they can start and run TheUstad from absolute paths outside the enrolled
repository. A relative path resolves inside the repository Claude is editing,
so the plugin does not trust one.

## 2. Enroll a repository

From your own terminal, not through Claude:

```bash
python3 ~/theustad/theustad.py enroll --repo /path/to/project --calibrate
```

Plugin users can run the same command against the plugin's copy;
`/theustad:status` prints the exact path. Enrollment writes the policy under
`~/.theustad`, outside the repository:

- the verifier,
- the protected patterns,
- the verifier deadline,
- how many times a Stop may be blocked.

`--calibrate` runs the verifier three times first and refuses a deadline it
cannot meet.

**Name the verifier your project actually uses.** The default is isolated
pytest under the interpreter that ran `enroll`, and that interpreter has to
be able to import your project and pytest:

```bash
python3 ~/theustad/theustad.py enroll --repo /path/to/project \
  --verifier "/path/to/project-venv/bin/python -m pytest -q" --calibrate
```

Then start a **new** Claude Code session in the repository and run `/hooks`
to confirm both hooks are listed. A policy is copied into each session when it
starts, so enrolling or re-enrolling never changes a session already running.

`status --repo PATH` shows the enrolled policy and one `CLAUDE_HOOKS` state:

- `installed`
- `not-installed`
- `stale`: a handler cannot start, names a relative path, or is not the
  command `install-hooks` writes
- `unsafe`: a handler runs TheUstad from inside that repository

Run `install-hooks` again, from a clone outside the repository, to fix either
of the last two. `unenroll --repo PATH --yes` removes the policy.

## 3. What a session looks like

| Claude's last message | Verifier | Result |
|---|---|---|
| Claims completion | passes, census intact | Stop allowed; `VERIFIED` with the audit root |
| Claims completion | fails | Stop blocked; Claude sees the failing output |
| Anything | protected file changed | Stop blocked; file restored; `TAMPERED` |
| Background task still running | not run yet | Stop deferred: `BACKGROUND_ACTIVE` |
| Blocked too often | | `FINAL RETRY_EXHAUSTED`; never reported as `VERIFIED` |

Every event is appended to one SHA-256 audit chain per session. `verify-chain
--repo PATH` checks it.

## Limits

- **Same-user boundary.** The policy and snapshots live outside the
  repository, but a process running as you can still edit them. TheUstad is a
  repository-level anti-tampering harness, not an operating-system security
  boundary.
- **A repository can try to switch hooks off.** A project's
  `.claude/settings.json` can set `disableAllHooks`. Only managed policy
  settings, wrapper mode, or [the CI check](CI.md) close that gap. Use the CI
  check as the backstop that does not depend on the session.
- **Claude Code ends a turn after eight consecutive stop-hook
  continuations.** TheUstad's own limit is five blocks by default
  (`--max-blocks`), and it records `RETRY_EXHAUSTED` rather than ever reporting
  success.
- **POSIX.** Hook mode is supported on Linux, macOS and WSL 2.
- The plugin installs a copy of the whole repository (about 9 MB).
