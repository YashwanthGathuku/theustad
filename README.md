# Gate v2

Gate is a verification-and-retry runtime for `codex exec`. It watches the
agent's final completion claim, protects trusted test inputs, runs an isolated
verifier, returns failure evidence to the same Codex thread, and writes a
SHA-256 chained audit log.

## OpenAI Build Week submission

- Devpost: https://devpost.com/software/gate-0lypv2
- Current deterministic-fixture demo: https://youtu.be/kGGdz649zCQ
- Live real-project video: [`docs/video/gate-real-project-live.mp4`](docs/video/gate-real-project-live.mp4)
- Video timeline and integrity: [`docs/video/README.md`](docs/video/README.md)
- Real-project recording procedure: [`docs/demo/README.md`](docs/demo/README.md)
- Before/after comparison evidence: [`docs/evidence/real_project_demo`](docs/evidence/real_project_demo/README.md)
- Permanent release evidence: [`docs/evidence`](docs/evidence)
- Anchored rehearsal root:
  `200042504cd90869d2bc8edcd60278049e231ead88ae69a60919a64a335d4a20`

## Supported platforms

- Python 3.10 or newer.
- Linux and macOS are supported.
- On Windows, run Gate inside WSL 2. Native Windows process-tree termination
  is not supported and must not be presented as supported behavior.
- Runtime code uses only the Python standard library. Pytest is the development
  and default verifier dependency.

## Quick start

For the Codex plugin, install once from a supported shell:

```bash
git clone https://github.com/YashwanthGathuku/gate.git
cd gate
python3 -m venv "$HOME/.local/share/gate/plugin-venv"
GATE_PYTHON="$HOME/.local/share/gate/plugin-venv/bin/python"
"$GATE_PYTHON" -m pip install --upgrade pip pytest
"$GATE_PYTHON" scripts/install_plugin.py
codex plugin list --json
```

Restart Codex, open a real Git project, and invoke `$gate:doctor`, `$gate:run`,
then `$gate:audit`. The complete installation, Codex UI, WSL 2, real-project,
update, and troubleshooting workflow is in
[`docs/PLUGIN_GUIDE.md`](https://github.com/YashwanthGathuku/gate/blob/master/docs/PLUGIN_GUIDE.md).

## Choose an interface

Gate has two invocation paths. They package the same `gate.py` and `gatelib/`
core and produce the same verdicts and audit-chain format.

| Interface | Best for | Entry point |
|---|---|---|
| **Codex plugin** | Developers working inside Codex who want named commands and automatic external state paths | `$gate:doctor`, `$gate:run`, `$gate:audit` |
| **Standalone CLI** | CI, shell automation, security review, and environments that do not install Codex plugins | `python gate.py --repo ... --task ...` |

The plugin is a convenience and adoption layer, not a second verifier. It
delegates security-sensitive work to the bundled standalone core. Use either
interface for a run; do not launch both against the same working tree at once.

## Standalone CLI

Create an environment in a Linux, macOS, or WSL 2 shell and run the tests:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip pytest
python -m pytest tests -q
```

Then run Gate against a Git repository and an explicit task file:

```bash
python /absolute/path/to/gate/gate.py \
  --repo /absolute/path/to/project \
  --task /absolute/path/to/task.md
```

Gate prints `FINAL`, `AUDIT_LOG`, and `AUDIT_ROOT`. Only exit code `0` with
`FINAL VERIFIED` is success. Validate the emitted log independently with
`verify_chain.py` as shown under [Audit verification](#audit-verification).

## Codex plugin

The Gate plugin packages the runtime outside the repository being modified and
adds three Codex skills: `$gate:doctor`, `$gate:run`, and `$gate:audit`. A Gate
run starts a separate Gate-controlled child Codex session; it does not claim to
retroactively protect the conversation that launched it.

Install the local package from a Linux, macOS, or WSL 2 checkout using the
external trusted environment from [Quick start](#quick-start):

```bash
git clone https://github.com/YashwanthGathuku/gate.git
cd gate
"$GATE_PYTHON" scripts/install_plugin.py
codex plugin list --json
```

The installer copies an allowlisted runtime to `~/plugins/gate`, preserves
unrelated entries in `~/.agents/plugins/marketplace.json`, and runs
`codex plugin add gate@personal --json`. Restart Codex if the installed skills
do not appear immediately.

In Codex Desktop on Linux or macOS, open the target repository and enter the
skill prompts below in a new task. On a Windows host, run the successful coding
workflow from the Codex terminal UI inside WSL 2; native Windows Desktop can
discover the plugin and validate existing logs but `$gate:doctor` and
`$gate:run` intentionally fail closed. See the
[plugin guide](https://github.com/YashwanthGathuku/gate/blob/master/docs/PLUGIN_GUIDE.md#windows-with-wsl-2)
for copy-paste setup.

From any supported Git repository, invoke the skills in Codex:

```text
$gate:doctor Check whether this repository is ready for Gate.
$gate:run Implement the requested task and report the exact Gate verdict.
$gate:audit Verify /absolute/path/to/audit_YYYYmmdd_HHMMSS.jsonl.
```

`$gate:run` does not edit the repository from the parent conversation. It
launches the bundled runtime, which freezes protected inputs before starting a
separate child, resumes that exact child thread with verifier evidence, and
returns Gate's terminal verdict and audit root without reinterpretation. Only
child exit code 0 plus `FINAL VERIFIED` is successful completion.

Native Windows installation is allowed so users can inspect the package, but
`$gate:doctor` and `$gate:run` fail closed there. Use WSL 2 because Gate v2's
contract requires POSIX process-group termination. `$gate:audit` can validate
an existing chain on native Windows because it does not start an agent.

Remove the local installation with:

```bash
codex plugin remove gate@personal --json
```

For judging, install the plugin, run `$gate:doctor`, start one real task through
`$gate:run`, and validate the emitted log with `$gate:audit`. The deterministic
adversarial rehearsal below remains the repeatable proof of
`FALSIFIED -> TAMPERED -> VERIFIED`; the plugin workflow demonstrates that the
same Gate core is installable and usable from an active developer project.

## License and attribution

Gate is licensed under **GPL-3.0-or-later**, replacing the earlier MIT license
for releases from this commit forward. When distributing Gate or a derivative,
preserve the copyright and attribution notices, include the license, mark
changes, and provide corresponding source as required by GPLv3. See
[`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

`NOTICE` applies a reasonable author-attribution preservation term under
GPLv3 section 7(b) to redistributed copies and derivatives.

The license does not require someone who only runs an unmodified private copy
to publish a credit statement. The redistribution obligations provide the
enforceable credit and source-preservation behavior intended for downstream
copies and forks.

Copies already received under the repository's earlier MIT license retain
that existing grant; release `0.2.0` and later are distributed under the GPL
terms above.

## Real-project recording demo

The recording walkthrough uses the real
[`pytest-dev/iniconfig`](https://github.com/pytest-dev/iniconfig) repository at
a pinned commit with a human-authored acceptance test. It includes separate,
copy-paste paths for the Codex plugin and original standalone CLI, plus a
two-minute shot list and honesty labels:

[`docs/demo/README.md`](docs/demo/README.md)

The checked-in
[`live recording`](docs/video/gate-real-project-live.mp4) shows the ordinary
control run, plugin installation, live `$gate:run`, exact verified child, audit
validation, and the final before/after comparison. Its full transcripts and
audit are under
[`docs/evidence/real_project_video`](docs/evidence/real_project_video/README.md).

The captured comparison uses three clean clones of the same pinned project:

| Mode | Independent result | Verification evidence |
|---|---:|---|
| Ordinary Codex without Gate | 50 passed | No Gate verdict, audit log, or root |
| Standalone Gate CLI | 51 passed | `FINAL VERIFIED` plus independently valid SHA-256 chain |
| Installed Gate plugin | 50 passed | `$gate:run` verified, then `$gate:audit` validated the chain |

Ordinary Codex solved the task. Gate's demonstrated value is the protected,
independent completion decision and portable audit record, not a claim that it
improves the generated implementation. The plugin provides that same core
inside the developer's active Codex workflow; the CLI remains available for
automation and direct review.

For a clean checkout, give the target fixture its own Git history before a
live Codex run:

```bash
python fake_codex.py reset --repo demo_repo
git -C demo_repo init
git -C demo_repo add -A
git -C demo_repo commit -m "seed: broken duration fixture"
```

The seeded fixture has 11 tests and intentionally starts with one failure:
`parse_duration("90m")`.

## Deterministic adversarial rehearsal

`demo3` is a **deterministic scripted adversarial rehearsal**, not a live AI
run. Its reasoning and final messages are scripted. Its source edits, test
deletion, and pytest subprocesses are real.

Reset the fixture, then run the rehearsal from the Gate repository root:

```bash
python fake_codex.py reset --repo demo_repo
python gate.py --repo demo_repo --task task.md \
  --cmd "python ../fake_codex.py demo3" \
  --resume-cmd "python ../fake_codex.py demo3 --resume {thread_id}" \
  --max-retries 3 --no-color
```

The expected verdict sequence is:

```text
FALSIFIED -> TAMPERED -> VERIFIED
```

Round 1 makes the narrow parser fix and passes only parser tests; Gate's full
verifier exposes two invoice regressions. Round 2 deletes the invoice test and
gets a genuinely green local run; Gate detects and restores the protected
file. Round 3 moves canonical invoice validation into `invoice.py`, and the
full 11-test suite passes.

Two additional scripted scenarios are available:

- `naive2`: `FALSIFIED -> VERIFIED`, without the deletion attack.
- `crash`: agent exit 2 becomes `AGENT_ERROR`, even if its final text claims
  completion.

Replace `demo3` in both command options to run either scenario.

## Live Codex run

The real run is separate from the scripted rehearsal. Authenticate the Codex
CLI, reset the fixture, and launch this from another terminal:

```bash
python fake_codex.py reset --repo demo_repo
python gate.py --repo demo_repo --task task.md
```

Gate uses the verified CLI forms `codex exec --json --sandbox workspace-write`
and `codex exec resume --json <thread_id>`. A live agent may be falsified and
resume with evidence, or it may produce the complete fix in round 1.

## Audit verification

Every run prints its timestamped audit path and final root:

```text
AUDIT_LOG /path/to/audit_YYYYmmdd_HHMMSS.jsonl
AUDIT_ROOT <sha256>
```

Validate the log independently:

```bash
python verify_chain.py /path/to/audit_YYYYmmdd_HHMMSS.jsonl
```

Anchor the printed root outside the log in both a pushed Git commit and the
submission text. Editing a chained record then becomes detectable relative to
that external anchor. Gate v2 does not claim HMAC, signing, or remote
attestation.

## Security contract and limits

Gate freezes tests, pytest configuration, conftest files, Python shadowing
paths, and startup customization files outside the target repository. It uses
an absolute interpreter with `-I -B -m pytest -q`; `-B` prevents the trusted
verifier from creating new protected bytecode under `tests/**`. Agent process
groups are stopped before checks, manifests are checked before and after the
verifier, timeouts are explicit, and only `VERIFIED` exits zero.

This is a repository-level anti-reward-hacking harness, not an operating-system
security boundary. Its limits are:

- Application code can detect tests or terminate the test process. Gate does
  not turn a weak verifier into a strong oracle.
- A hostile human or same-user process outside the Codex sandbox can attack
  Gate state.
- Kernel-level interference is out of scope.
- Protected baseline tests are immutable in v2. Legitimate edits and
  agent-authored trusted tests are not supported.
- Gate verifies only the configured invariant, not every meaning in the
  agent's prose.
- Native Windows, HMAC/signatures, remote attestation, multiple verifiers, and
  hook integration are roadmap work.

## Build provenance

The Gate core was built through Codex with GPT-5.6 from `docs/SPEC.md`. Codex
implemented the Prompt 0-7 core, tests, adversarial rehearsal, and evidence
documentation in build/feedback session
`019f708d-eb32-72d0-a58d-fdd5ffcff511`; the separate live `codex exec` coda
used thread `019f78cf-2302-7670-a725-6c89a41699c8`. The seeded fixture and
independent `verify_chain.py` oracle were supplied inputs. The excluded v1
prototype and private red-team scripts were not implementation inputs.
