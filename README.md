# TheUstad

[![Tests](https://github.com/YashwanthGathuku/theustad/actions/workflows/tests.yml/badge.svg)](https://github.com/YashwanthGathuku/theustad/actions/workflows/tests.yml)

> **Codex says "done." TheUstad checks whether that is true.**

When I use a coding agent, I give it a goal or a prompt to build something. It works for a while and eventually says, “It’s done.” But when I check the work, it is sometimes incomplete or the full test suite is still failing. A completion message is only a claim.

There is another problem: when a test keeps failing, an agent may change, weaken, or even delete that test instead of fixing the actual behavior. The test suite can become green while the underlying problem is still there.

## Why TheUstad exists

That is why I built TheUstad. “Ustad” means teacher. TheUstad does not simply trust the agent’s final message—it checks the evidence.

Before the agent starts, TheUstad creates a fingerprint of protected inputs, including tests and verifier configuration. It then captures the agent’s final message, detects completion claims, checks that the protected files have not changed, and runs the configured verifier itself.

If the agent says the work is complete but the verifier fails, the claim is marked FALSIFIED. If the agent changes or deletes a protected test, TheUstad marks the round TAMPERED, restores the original files, and sends the evidence back into the same Codex session so the agent can try again. Only an explicit completion claim supported by a passing verifier becomes VERIFIED.

TheUstad also handles missing completion claims, incomplete work, agent crashes, and timeouts. Every round is written to a hash-chained audit log.

VERIFIED does not mean that the software is guaranteed to be bug-free. It means that the agent’s completion claim matched the verifier selected by the user, with the protected inputs still intact.



- [OpenAI's monitoring of internal coding agents](https://openai.com/index/how-we-monitor-internal-coding-agents-misalignment/)
  documents rare but high-severity reward-hacking behavior, including test edits.
- [METR's Claude 3.7 evaluation](https://metr.org/evaluations/claude-3-7-report/)
  includes a software-engineering run that edited a provided test to pass.
- The [2025 Stack Overflow Developer Survey](https://survey.stackoverflow.co/2025/ai)
  reports substantial developer distrust of AI-tool accuracy.
- [DORA's analysis of AI-assisted development](https://dora.dev/insights/balancing-ai-tensions/)
  describes the verification work that can offset faster code generation.
- [Are "Solved Issues" in SWE-bench Really Solved Correctly?](https://arxiv.org/html/2503.15223v1)
  reports plausible patches that failed fuller developer-written validation.

TheUstad does not make software 100% correct. A verifier can only establish the
protected, configured checks it runs; human review and strong acceptance tests
remain necessary.

## What changes with TheUstad

| Without TheUstad | With TheUstad |
|---|---|
| Agent prose ends the task | A completion claim triggers verification |
| Agent-selected checks decide acceptance | A trusted, configured verifier decides the result |
| Test and verifier inputs can change unnoticed | Protected inputs are frozen, checked, and restored |
| A retry can lose the original context | Evidence resumes the exact child thread |
| The result is chat output | The result includes `FINAL`, `AUDIT_LOG`, and `AUDIT_ROOT` |

The standalone CLI and Codex plugin use the same enforcement core. The plugin
is an allowlisted copy of `theustad.py` and `theustadlib/`, not a separate or
weaker verifier.

TheUstad succeeds when completion becomes falsifiable and reproducible rather
than accepted solely from an agent's prose.

## Three-minute proof

The reproducible `demo3` fixture is a **deterministic scripted adversarial rehearsal**,
not a live AI run. Its reasoning and final messages are scripted;
its source edits, protected-test deletion, verifier subprocesses, restoration,
and audit records are real.

```bash
python fake_codex.py reset --repo demo_repo
python theustad.py --repo demo_repo --task task.md \
  --cmd "python ../fake_codex.py demo3" \
  --resume-cmd "python ../fake_codex.py demo3 --resume {thread_id}" \
  --max-retries 3 --no-color
```

It produces `FALSIFIED -> TAMPERED -> VERIFIED`. `PASS_NO_CLAIM` is neutral,
not a successful completion. The rehearsal demonstrates explicit protection
and recovery mechanics; it does not select a project's verification framework.

## Quick start

Run these commands from Linux, macOS, or WSL 2. Clone the canonical repository
and create the trusted environment outside the repository that TheUstad will
verify:

```bash
git clone https://github.com/YashwanthGathuku/theustad.git
cd theustad
python3 -m venv "$HOME/.local/share/theustad/plugin-venv"
THEUSTAD_PYTHON="$HOME/.local/share/theustad/plugin-venv/bin/python"
"$THEUSTAD_PYTHON" -m pip install --upgrade pip pytest
"$THEUSTAD_PYTHON" scripts/install_plugin.py
codex plugin list --json
```

The list must show `theustad@personal` as installed and enabled. Restart Codex
after installation, then follow [the plugin guide](docs/PLUGIN_GUIDE.md).

## Choose an enforcement mode

| Interface | Assurance | Use it for | Entry point |
|---|---|---|---|
| Standalone wrapper | Highest | CI, automation, direct review | `python theustad.py --repo ... --task ...` |
| Codex plugin | Highest | A protected child coding task in Codex | `$theustad:doctor`, `$theustad:run`, `$theustad:audit` |
| Claude Code hook (experimental) | Guardrail | Automatic verification when Claude tries to stop | `theustad.py enroll` + `SessionStart`/`Stop` hooks |

Use one interface per working tree at a time. All modes use the same protected
verifier concepts and SHA-256 audit-chain format.

Wrapper mode remains the strongest boundary because TheUstad owns and
terminates the agent process. Hook mode depends on the host actually invoking
the configured hook and is therefore an automatic guardrail, not an
independent process boundary.

## Standalone CLI

Install the default verifier dependency and run the repository suite:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip pytest
python -m pytest tests -q
```

Run TheUstad against an explicit Git repository and task file:

```bash
python theustad.py --repo /absolute/path/to/project \
  --task /absolute/path/to/task.md
```

Only exit code `0` with `FINAL VERIFIED` is successful completion. See the
[real-project reproduction guide](docs/demo/README.md) for ordinary Codex,
CLI, and plugin paths.

## Codex plugin

The plugin starts a separate TheUstad-controlled child; the parent task is only
a launcher and result viewer. In a fresh Codex task, run:

```text
$theustad:doctor Check this Git repository using the trusted absolute Python.
$theustad:run Implement the task in /absolute/path/to/task.md and report CHILD_THREAD, FINAL, AUDIT_LOG, and AUDIT_ROOT exactly.
$theustad:audit Verify /absolute/path/to/audit_YYYYmmdd_HHMMSS.jsonl.
```

Remove the canonical package with:

```bash
codex plugin remove theustad@personal --json
```

## Experimental Claude Code hook mode

Hook mode keeps invocation authority in user-level configuration instead of
asking the agent to call TheUstad. `SessionStart` freezes protected inputs into
external state; `Stop` loads that same session baseline, checks tampering,
runs the fixed enrolled verifier, and returns failure evidence with exit code
2 so Claude continues working.

```bash
python theustad.py enroll --repo /absolute/path/to/project
# Merge the emitted JSON into ~/.claude/settings.json.
# Start a new Claude Code session in the enrolled repository, then use /hooks
# to confirm both commands come from User Settings.
```

The hook entry point refuses `--verifier`, `--repo`, `--protect`, timeout, and
state arguments. It binds the initial `session_id` to the enrolled repository,
preserves the original baseline across resume/compact `SessionStart` events,
uses Claude's documented `last_assistant_message` Stop field, defers while
background or scheduled session work is pending, checks protected inputs before
and after verification, and appends every event to one continuous validated
audit chain.

Only the Claude Code adapter is implemented. Its fixtures follow the current
[official hook schema](https://code.claude.com/docs/en/hooks), but a real local
schema capture and live-fire run are still required before calling a specific
Claude Code version tested. Codex and other vendor hook adapters remain
unimplemented until their real payloads and enforcement semantics are captured.
See the [hook-mode and local Codex guide](docs/HOOK_MODE_GUIDE.md).
The [prototype review](docs/HOOK_MODE_REVIEW.md) records which supplied ideas
were retained, which attacks were reproduced, and why the old files were not
copied directly.

## Custom verifiers and protected inputs

The default verifier is pytest from the trusted absolute interpreter in
isolated mode. Supply an explicit custom verifier when the project requires a
different acceptance command; the command is parsed as argv and never needs a
shell:

```bash
python theustad.py --repo /absolute/path/to/project \
  --task /absolute/path/to/task.md \
  --verifier "npm test" \
  --protect-add package.json package-lock.json
```

The custom verifier is the acceptance oracle for that run. Protect all inputs
it needs before starting; protected files are checked before and after
verification, and changed inputs are restored and reported as `TAMPERED`.

TheUstad starts both the agent and the verifier with
`PYTHONDONTWRITEBYTECODE=1`. Without it, an ordinary `pytest` run writes
`tests/__pycache__/*.pyc` inside the protected tree, and the very next manifest
check reports an honest round as `TAMPERED`. A `.pyc` file that TheUstad did not
cause is still reported, so planted bytecode remains detectable.

If the configured patterns match nothing, TheUstad prints `PROTECTED 0 paths`
with a warning and records it in the audit chain: a run with an empty baseline
can never reach `TAMPERED`, so its `VERIFIED` result carries no anti-tampering
guarantee.

On WSL, make sure every custom-verifier executable is WSL-native before
starting TheUstad. For example, check both `command -v node` and
`command -v npm`, then inspect their real paths with `readlink -f`. A path under
`/mnt/c` is a Windows tool and may be unable to verify a repository or temporary
state held in the Linux filesystem. Fix the WSL `PATH` or install the Linux
toolchain instead of treating that environment failure as a code verdict.

## Audit verification

Every run reports an `AUDIT_LOG` and `AUDIT_ROOT`. Validate the exact emitted
log independently:

```bash
python verify_chain.py /absolute/path/to/audit_YYYYmmdd_HHMMSS.jsonl
```

Anchor the printed SHA-256 root outside the log, such as in a pushed commit or
release record. TheUstad does not claim signing, HMAC, or remote attestation.

## Evidence and reproducibility

The current submission, narrated demo, and release evidence are available for
review:

- Current 70-second narrated TheUstad demo and [publication evidence](docs/evidence/theustad-1.0/publication.txt): https://youtu.be/D1nlvLk9iv8
- Current video files, digest, and captions: [docs/video/README.md](docs/video/README.md)
- Reproducible adversarial matrix and audit chains: [docs/evidence](docs/evidence/README.md)

### Verified release results

These results were captured from a fresh WSL clone. Every retained transcript
and audit record is covered by `robustness/sha256sums.txt`.

| Check | Attack or success path | Observed result |
|---|---|---|
| A1 | Agent weakens a protected assertion | `TAMPERED`; file restored |
| A2 | Agent plants a root configuration hook | `TAMPERED`; file removed |
| A3 | Agent explicitly claims completion while the suite is red | `FALSIFIED` |
| A4 | Agent process crashes | `AGENT_ERROR` |
| A5 | Agent poisons verifier configuration | `TAMPERED`; file restored |
| B1 | JavaScript project with an explicit npm verifier | `VERIFIED` |
| B2 | Honest one-round Python repair | `VERIFIED` |
| B3 | Ten deterministic adversarial runs | All ten produced `FALSIFIED -> TAMPERED -> VERIFIED` |
| B4 | One copied audit record is edited | Edited copy `BROKEN`; original `VALID` |

The release suites recorded `188 passed, 4 skipped` on native Windows and
`192 passed` on WSL. The Windows skips cover POSIX process-group and symlink
behavior exercised by the complete WSL run. The B3/B4 original audit root is:

```text
d16ed29de2e6408f5ed1a520759caa1cdd40236f5006cc2f001ba9c7caf96aab
```

The AGPL release update added a license regression check; the native Windows
suite then recorded `189 passed, 4 skipped`. A fresh Codex process loaded
`$theustad:doctor` from the refreshed cache-busted package and independently
reported `AGPL-3.0-or-later`. The exact package version and captured Codex task
ID are recorded in
[`agpl_release_validation.txt`](docs/evidence/theustad-1.0/agpl_release_validation.txt).
The earlier `$theustad:audit` chain-validation proof remains captured in
[`plugin_codex_audit.txt`](docs/evidence/theustad-1.0/plugin_codex_audit.txt).

The final transactional-installer and cross-platform CI hardening pass recorded
`191 passed, 4 skipped` on native Windows and `194 passed, 1 skipped` on WSL
with a WSL-native verifier toolchain. Its independent 18-scenario matrix exited
`0`; see [`final_release_check.txt`](docs/evidence/theustad-1.0/final_release_check.txt).

### Three-minute video scope

The video does not need to replay all 18 checks. It should visibly prove four
things: an explicit false claim becomes `FALSIFIED`, protected-input poisoning
becomes `TAMPERED` and is restored, a legitimate custom verifier can reach
`VERIFIED`, and changing an audit record makes the copied chain `BROKEN` while
the anchored original remains `VALID`. The complete matrix stays here and in
the committed evidence for judges who want to inspect every run.

## Supported platforms

- Python 3.10 or newer.
- Linux, macOS, or WSL 2 for coding runs.
- Native Windows `doctor` and `run` fail closed; `$theustad:audit` can inspect
  an existing audit chain there.
- Runtime code uses only the Python standard library; pytest is the default
  verifier and development dependency.

## Security boundaries

TheUstad resolves a trusted absolute Python, uses isolated mode and `shell=False`,
freezes configured inputs, terminates the agent process group, checks manifests
before and after the verifier, resumes the exact thread ID, and records a final
claim classification. It is a repository-level anti-tampering harness, not an
operating-system security boundary against a hostile user, process, or kernel.

`VERIFIED` means the explicit custom verifier or default protected verifier
passed after a completion claim. It does not prove every product requirement or
guarantee absence of defects.

Hook mode has a narrower boundary. User-level policy and snapshots live outside
the repository, but a same-OS-user agent with unrestricted filesystem access
can still modify them. A repository can also attempt to disable non-managed
Claude hooks. TheUstad protects project hook files as defense in depth when the
Stop hook still runs, but only managed host policy, wrapper mode, or CI can
address the bootstrap case where the host never invokes TheUstad. Retry
exhaustion is recorded and surfaced as `FINAL RETRY_EXHAUSTED`; it is never
renamed `VERIFIED`.

## License and attribution

TheUstad is licensed under [AGPL-3.0-or-later](LICENSE). Preserve the license,
copyright, source, and attribution notices described in [NOTICE](NOTICE) when
redistributing modified copies. If you run a modified version as a network
service, GNU AGPL section 13 requires offering its Corresponding Source to users
who interact with it remotely. Private use of an unmodified copy does not
require a public endorsement or credit post.

## OpenAI Build Week

TheUstad was prepared for OpenAI Build Week with Codex and GPT-5.6. The public
repository, plugin, CLI, narrated demo, and reproducible evidence all use the
same TheUstad identity and enforcement core.
