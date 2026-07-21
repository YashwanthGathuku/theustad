# TheUstad

> **Codex says "done." TheUstad checks whether that is true.**

TheUstad is a verification-and-retry runtime for coding agents. It treats an
agent's completion message as a claim, protects configured inputs, runs a
trusted verifier, returns evidence to the exact child session, and records a
tamper-evident audit chain.

## Why TheUstad exists

An agent can write code, select a convenient test, and announce success inside
one trust boundary. TheUstad separates generation from acceptance by requiring
protected evidence before it accepts a completion claim.

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

## Choose CLI or Codex plugin

| Interface | Use it for | Entry point |
|---|---|---|
| Standalone CLI | CI, automation, direct review | `python theustad.py --repo ... --task ...` |
| Codex plugin | A protected coding task in Codex | `$theustad:doctor`, `$theustad:run`, `$theustad:audit` |

Use one interface per working tree at a time. Both write the same verdicts and
SHA-256 audit-chain format.

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

The Codex app installation smoke test reported
`1.0.0+codex.20260721091305` installed and enabled. A fresh Codex process then
loaded `$theustad:audit` from that exact cache-busted package and validated the
12-record chain above with exit code `0`. The captured Codex task ID is
`019f83f4-58e2-7ab2-9e46-3ce269eb9356`.

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

## License and attribution

TheUstad is licensed under [GPL-3.0-or-later](LICENSE). Preserve the license,
copyright, source, and attribution notices described in [NOTICE](NOTICE) when
redistributing modified copies.

## OpenAI Build Week

TheUstad was prepared for OpenAI Build Week with Codex and GPT-5.6. The public
repository, plugin, CLI, narrated demo, and reproducible evidence all use the
same TheUstad identity and enforcement core.
