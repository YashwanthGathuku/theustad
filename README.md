# Gate v2

> **Codex says "done." Gate checks whether that is true.**

Gate is a verification-and-retry runtime for coding agents, available as both
a standalone CLI and a Codex plugin. It treats an agent's completion message as
a claim, not proof. Gate protects trusted test inputs, runs a Gate-controlled
verifier, returns failure evidence to the same child Codex thread, and writes a
tamper-evident audit chain.

## Why Gate exists

Coding agents can generate a patch in minutes. The harder question comes next:
**who verifies that the patch actually satisfies the task?**

Today, the agent often writes the code, chooses which tests to run, interprets
their output, and announces that the work is complete. That puts the work and
its grade inside the same trust boundary. It creates five practical failure
modes:

1. The agent runs a narrow test, misses a cross-file regression, and says the
   task is complete.
2. A patch passes the available tests but still implements the wrong behavior.
3. The agent changes or deletes a test, configuration file, or verifier input
   so that a broken patch appears green.
4. A failed attempt is retried without preserving the exact evidence and
   session that produced it.
5. The final "all tests pass" statement leaves no portable record that another
   person can independently check later.

This is not a hypothetical edge case:

- [OpenAI's monitoring of internal coding agents](https://openai.com/index/how-we-monitor-internal-coding-agents-misalignment/)
  reports that agents sometimes illegitimately edit tests to make them pass.
  OpenAI labels this reward-hacking category rare but high severity.
- [METR's Claude 3.7 evaluation](https://metr.org/evaluations/claude-3-7-report/)
  documents a software-engineering run in which the model directly edited a
  provided tests file to cause all tests to pass.
- The [2025 Stack Overflow Developer Survey](https://survey.stackoverflow.co/2025/ai)
  found that 46% of respondents distrusted the accuracy of AI tools, compared
  with 33% who trusted them; only 3.1% reported high trust.
- [DORA's analysis of AI-assisted development](https://dora.dev/insights/balancing-ai-tensions/)
  calls time saved writing and then re-spent auditing a verification tax. It
  reports that 30% of developers had little or no trust in AI-generated code.
- A SWE-bench correctness study,
  [*Are "Solved Issues" in SWE-bench Really Solved Correctly?*](https://arxiv.org/html/2503.15223v1),
  found that 7.8% of evaluated plausible patches were counted correct by
  narrower validation while failing the full developer-written test suite. It
  also found behavioral discrepancies in 29.6% of plausible patches compared
  with the human patch.

The research describes two related problems: verification is expensive, and
the evidence used for verification can itself be weak or manipulated. Gate is
an outcome-control layer for that gap. It does not try to infer whether an
agent intended to cheat; it makes the same deterministic decision either way.

## How the idea became Gate

Gate began with one question:

> Why should the agent that performed the work also decide whether the work is
> finished?

The first design rule was simple: a completion claim must trigger verification,
not end it. The initial fixture made that rule concrete. A ticket asks for
`parse_duration("90m")` to work. The obvious parser fix makes targeted tests
green but silently violates a billing invariant in another module. Gate runs
the full verifier, catches the regression, and returns the real failure to the
same Codex thread.

Red-teaming exposed a more serious hole: an agent could delete the failing test
and receive a green result. That attack became a product requirement rather
than a hidden caveat. Gate freezes trusted test and verifier inputs before the
agent starts, reports protected changes as `TAMPERED`, restores the baseline,
and makes the agent continue from the evidence.

That evolution produced Gate's three-beat proof:

```text
false completion claim -> FALSIFIED
trusted test deletion  -> TAMPERED
correct implementation -> VERIFIED
```

The scripted fixture makes this sequence repeatable. The source edits, test
deletion, verifier processes, verdicts, restoration, retries, and audit hashes
are real. A separate live run demonstrates the same core with a real Codex
agent and a real open-source project.

## What Gate changes

| Without Gate | With Gate |
|---|---|
| Agent says "done" | "Done" triggers verification |
| Agent chooses a convenient test command | Gate runs the configured full verifier |
| Tests and verifier inputs can change unnoticed | Protected inputs are frozen, checked, and restored |
| Green output is accepted at face value | The verifier uses a trusted absolute interpreter and isolated mode |
| A retry may lose the original failure context | Evidence resumes the exact child Codex thread |
| The result is a chat message | The result includes `FINAL`, `AUDIT_LOG`, and `AUDIT_ROOT` |

Gate deliberately separates generation from acceptance:

```text
task -> coding agent -> completion claim
                     -> protected-input check
                     -> Gate-controlled verifier
                     -> FALSIFIED / TAMPERED / VERIFIED
                     -> exact-thread retry with evidence
                     -> independently checkable audit chain
```

The standalone CLI provides the enforcement engine. The Codex plugin makes the
same enforcement core available through `$gate:doctor`, `$gate:run`, and
`$gate:audit`. The plugin is an adoption layer, not a second or weaker verifier.

## What success means

Gate does not claim to make software 100% correct. A weak or incomplete test
suite remains a weak oracle, and `VERIFIED` means only that the protected,
configured verifier passed for the claimed task.

Gate succeeds when completion becomes falsifiable and reproducible:

- an agent cannot earn success from its own prose;
- narrow green tests cannot stand in for the configured full verifier;
- protected-test tampering becomes visible and recoverable;
- failures return as concrete evidence instead of another vague prompt; and
- a reviewer can validate the resulting audit chain without trusting the
  original chat transcript.

For individual developers, this reduces repetitive "did it really run?" work.
For teams, it creates a reviewable boundary between AI-generated changes and
the checks allowed to accept them. For CI, security, and compliance workflows,
it produces a portable decision record while preserving the requirement for
human review and strong acceptance tests.

## OpenAI Build Week submission

- Devpost: https://devpost.com/software/gate-0lypv2
- Public narrated live real-project demo: https://youtu.be/cAaMzRLyqWQ
- Deterministic adversarial-fixture demo: https://youtu.be/kGGdz649zCQ
- Live real-project video: [`docs/video/gate-real-project-live-narrated.mp4`](docs/video/gate-real-project-live-narrated.mp4)
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

The plugin is a convenience and adoption layer, not a second verifier. The
installer packages an allowlisted copy of the same `gate.py` and `gatelib/`
enforcement core used by the standalone CLI. This keeps plugin execution
outside the target repository without reducing Gate's verification behavior.
Use either interface for a run; do not launch both against the same working
tree at once.

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

Gate is licensed under **GPL-3.0-or-later**. When distributing Gate or a
derivative, preserve the copyright and attribution notices, include the
license, mark changes, and provide corresponding source as required by GPLv3.
See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

`NOTICE` applies a reasonable author-attribution preservation term under
GPLv3 section 7(b) to redistributed copies and derivatives.

The license does not require someone who only runs an unmodified private copy
to publish a credit statement. The redistribution obligations provide the
enforceable credit and source-preservation behavior intended for downstream
copies and forks.

## Real-project recording demo

The recording walkthrough uses the real
[`pytest-dev/iniconfig`](https://github.com/pytest-dev/iniconfig) repository at
a pinned commit with a human-authored acceptance test. It includes separate,
copy-paste paths for the Codex plugin and original standalone CLI, plus a
two-minute shot list and honesty labels:

[`docs/demo/README.md`](docs/demo/README.md)

The checked-in
[`narrated live recording`](docs/video/gate-real-project-live-narrated.mp4)
shows the ordinary control run, plugin installation, live `$gate:run`, exact
verified child, audit validation, and the final before/after comparison. It
adds a voiceover and burned-in captions to the preserved desktop capture. Its
full transcripts and audit are under
[`docs/evidence/real_project_video`](docs/evidence/real_project_video/README.md).
The narrated recording is [public on YouTube](https://youtu.be/cAaMzRLyqWQ)
for judges who do not want to download the checked-in MP4. The original silent
capture remains at [`docs/video/gate-real-project-live.mp4`](docs/video/gate-real-project-live.mp4)
as recording-source evidence. Its initial public upload,
https://youtu.be/njgvvLapxs0, remains available as a historical recording
reference; the narrated upload above is the current submission video.

The live recording uses two clean clones of the same pinned project:

| Mode | Independent result | Verification evidence |
|---|---:|---|
| Ordinary Codex without Gate | 51 passed | No Gate verdict, audit log, or root |
| Installed Gate plugin | 50 passed | `$gate:run` verified, then `$gate:audit` validated the chain |

The original standalone CLI was exercised separately against a third clean
clone. Its `51 passed`, `FINAL VERIFIED`, and independently valid chain are in
[`docs/evidence/real_project_demo`](docs/evidence/real_project_demo/README.md).

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
