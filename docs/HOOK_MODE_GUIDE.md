# Build and live-test TheUstad hook mode from local Codex

This guide deliberately separates two tools:

- **Codex CLI** is the coding environment used to inspect, review, and continue
  development of this repository.
- **Claude Code** is the first lifecycle-hook host implemented by this branch.

There is no Codex lifecycle-hook adapter in this increment. Do not copy the
Claude parser and rename it: capture Codex's real event payloads and enforcement
semantics first.

## 1. Use WSL 2 on Windows

TheUstad's coding runs require POSIX process-group behavior. On a Windows host,
open Ubuntu under WSL 2 and keep the checkout, target repo, and trusted Python
environment in the Linux filesystem (`~/...`), not under `/mnt/c`.

```bash
mkdir -p ~/code ~/.local/share/theustad
cd ~/code
git clone https://github.com/YashwanthGathuku/theustad.git
cd theustad
git switch -c feature/hook-mode-mvp
```

If you are applying a supplied patch, do it on this branch and inspect it
before running anything:

```bash
git apply --check /path/to/theustad-hook-mode.patch
git apply /path/to/theustad-hook-mode.patch
git status --short
git diff --stat
```

## 2. Prepare a trusted Python

Keep this interpreter outside any target repository that an agent will edit.

```bash
python3 -m venv ~/.local/share/theustad/hook-venv
THEUSTAD_PYTHON="$HOME/.local/share/theustad/hook-venv/bin/python"
"$THEUSTAD_PYTHON" -m pip install --upgrade pip pytest
"$THEUSTAD_PYTHON" -m pytest tests -q
```

Expected for this implementation in the build environment: `256 passed,
1 skipped`. Your count may increase as new tests land; any failure blocks the
live test.

## 3. Start local Codex in the repository

Install/update Codex using the current official instructions, then verify the
local client and authentication:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
codex --version
codex login status
codex doctor
cd ~/code/theustad
codex
```

Official Codex CLI guide: <https://developers.openai.com/codex/cli>.

Paste this as the first Codex task:

```text
Read README.md, docs/SPEC.md, docs/HOOK_SCHEMAS.md, and
docs/HOOK_MODE_GUIDE.md completely. Review the current branch; do not replace
the existing wrapper CLI. Verify that hook mode keeps policy outside the target
repo, binds session_id to the initial repo, preserves the baseline across
compact/resume SessionStart events, uses Claude Stop.last_assistant_message,
reopens one validated audit chain, checks tampering before and after the
verifier, and surfaces retry exhaustion as non-verified. Run the focused hook
tests and then the complete test suite. Report concrete failures with command
output before editing. Do not add a Codex hook adapter without live payload
fixtures.
```

Then ask Codex for a dedicated review:

```text
Review the uncommitted hook-mode diff as a security boundary. Attack cwd
changes, compaction re-freeze, policy argument injection, missing baselines,
same-session re-enrollment, audit rewrites, verifier-time tampering, symlinks,
and retry exhaustion. Add a regression test before each fix. Run the full
suite and paste the final summary.
```

## 4. Enroll a disposable target repository

Do not start with production code. Use a separate fixture or clone.

```bash
export THEUSTAD_HOME="$HOME/.theustad"
cd ~/code/theustad
"$THEUSTAD_PYTHON" theustad.py enroll \
  --repo "$HOME/code/disposable-target" \
  --max-blocks 5
```

For a non-pytest project, enroll an explicit argv-only verifier and protect its
inputs:

```bash
"$THEUSTAD_PYTHON" theustad.py enroll \
  --repo "$HOME/code/disposable-target" \
  --verifier "npm test" \
  --protect-add package.json package-lock.json
```

Only the user chooses these enrollment arguments. Hook invocations refuse
them. The policy is stored under `~/.theustad/enrollments/`; a session receives
a frozen copy so re-enrollment cannot change an active session.

## 5. Install the two Claude Code hooks

Merge the JSON printed by `enroll` into the user-level file
`~/.claude/settings.json`. Do not put invocation authority inside the target
repository. The emitted commands contain the absolute trusted Python and
absolute `theustad.py` path, with shell-safe quoting.

Start Claude Code from the enrolled repository and run `/hooks`. Confirm:

- `SessionStart` appears from **User Settings**;
- `Stop` appears from **User Settings**;
- both commands use the expected absolute paths.

The official Claude Code reference is
<https://code.claude.com/docs/en/hooks>. It documents that Stop exit code 2
prevents stopping and sends stderr back to Claude. It also documents an
eight-consecutive-block host ceiling; TheUstad caps enrollment at seven and
ends exhausted sessions with a visible red audit verdict.

## 6. Capture the installed version before claiming compatibility

The committed fixtures follow official documentation, not a live binary. In a
temporary user hook, capture stdin for one `SessionStart` and one `Stop` into a
directory outside the target repo. Record:

```bash
claude --version
```

Compare the redacted payloads with `docs/HOOK_SCHEMAS.md` and the fixtures under
`tests/fixtures/hooks/claude/`. If field names or types differ, update fixtures
first, then parser tests, then code. Never weaken the parser to substring-match
events such as `SubagentStop` or `StopFailure`.

## 7. Run the deterministic hook proof

Before a live agent, the full lifecycle is covered without network calls:

```bash
"$THEUSTAD_PYTHON" -m pytest \
  tests/test_enrollment.py \
  tests/test_hookadapter.py \
  tests/test_cli_hook.py \
  tests/test_hook_e2e.py -q
```

The suite proves:

| Scenario | Required result |
|---|---|
| Explicit claim + green verifier | `VERIFIED`, exit 0, visible audit root |
| Red verifier + claim | `FALSIFIED`, exit 2 with evidence |
| No claim + green verifier | `PASS_NO_CLAIM`, exit 0, explicitly not verified |
| Deleted or weakened test | `TAMPERED`, exit 2, baseline restored |
| Project hook-disable config planted | `TAMPERED`, restored if Stop still fires |
| Compaction after test weakening | original baseline preserved; `TAMPERED` |
| Stop from a subdirectory | original session-bound repo verified |
| Verifier changes protected input | post-verifier `TAMPERED` |
| Background task or scheduled wakeup is pending | `BACKGROUND_ACTIVE`; verifier is deferred |
| Hook `--verifier` injection | refused before state change |
| Retry ceiling reached | visible `FINAL RETRY_EXHAUSTED`, never `VERIFIED` |

## 8. Live-fire proof

From the enrolled disposable project:

```bash
claude
```

Give it a ticket whose tempting shortcut is to weaken or delete an acceptance
test. Record one complete sequence:

1. `SessionStart` creates the external baseline.
2. Claude changes a protected test and tries to stop.
3. TheUstad returns `TAMPERED`, restores the test, and exit 2 feeds evidence
   back.
4. Claude fixes application code and tries again.
5. TheUstad returns visible `VERIFIED` with `AUDIT_ROOT`.
6. Outside Claude Code, validate the session chain:

```bash
"$THEUSTAD_PYTHON" ~/code/theustad/theustad.py verify-chain \
  --repo "$HOME/code/disposable-target"
```

Save the Claude version, terminal recording, exact audit path/root, and full
test output before making a public compatibility claim.

## 9. Security claims you can and cannot make

You can say:

- the agent does not choose the hook verifier or protected patterns;
- protected repository inputs are checked before and after verification;
- repeated SessionStart events cannot overwrite the initial session baseline;
- audit records form one independently verifiable SHA-256 chain;
- a host-triggered Stop failure returns evidence automatically.

Do not say:

- hooks are an unskippable security boundary;
- external files are safe from an unrestricted same-user process;
- project hook-file protection can detect a hook that was disabled before it
  ran;
- Claude fixtures prove Codex, Cursor, Kiro, or another vendor;
- `VERIFIED` proves software is bug-free.

Use wrapper/plugin mode or CI for the strongest current boundary. Use managed
Claude settings where an organization needs project settings to be unable to
disable the hook.
