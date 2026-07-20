# Real-project Gate demo

This recording uses
[`pytest-dev/iniconfig`](https://github.com/pytest-dev/iniconfig), a real
MIT-licensed Python project maintained by the pytest organization. The demo is
pinned to upstream commit `77db208ab4ae0cd2061d909fe222a1db72867850` so the
setup and test output do not drift during recording.

The `__len__` feature is a compact maintenance task created for this demo. It
is not an existing upstream issue or a merged contribution. The failing test
is a human-authored acceptance test added before Gate starts, which makes it
part of Gate's protected baseline. Do not describe this as an upstream bug.

Use Linux, macOS, or WSL 2. Native Windows cannot truthfully demonstrate
Gate's required process-group termination behavior.

## Captured before-and-after result

The permanent transcripts are in
[`docs/evidence/real_project_demo`](../evidence/real_project_demo/README.md).
All three runs began from the same `1 failed, 49 passed` baseline.

| Workflow | Result | What the developer receives |
|---|---|---|
| Ordinary Codex without Gate | 50 tests passed | Agent output and a working-tree diff, but no independent verdict or audit |
| Original Gate CLI | `FINAL VERIFIED`, 51 tests passed | Protected verification plus a four-record audit chain |
| Gate Codex plugin | `FINAL VERIFIED`, 50 tests passed | The same protected core through `$gate:run`, plus `$gate:audit` |

The implementations are all correct. The comparison demonstrates Gate's real
job: deciding whether a completion claim is supported by protected evidence
and leaving a portable record. It does not claim that Gate makes Codex write
better code.

## Reproduce all three paths in WSL 2

The checked-in runners create three independent target clones so no workflow
inherits another workflow's changes. From a Linux-home Gate clone on branch
`Ash/gate-codex-plugin`:

```bash
bash docs/demo/prepare_wsl_demo.sh

codex plugin remove gate@personal --json || true
bash docs/demo/run_no_gate_wsl.sh
bash docs/demo/run_gate_cli_wsl.sh

$HOME/.local/share/gate-demo/gate-plugin-venv/bin/python \
  scripts/install_plugin.py
bash docs/demo/run_gate_plugin_wsl.sh
```

The runners write raw evidence to `$HOME/gate-demo-evidence` and Gate state to
`$HOME/.local/state/gate-demo`, both outside the target projects. Override the
documented environment variables in each script when using other locations.

## Prepare the real repository

Set absolute paths for the Gate checkout, target clone, and an external virtual
environment. Keeping the environment outside the target makes the repository
snapshot small and keeps the trusted interpreter out of the agent workspace.

```bash
export GATE_ROOT="$HOME/src/gate"
export DEMO_ROOT="$HOME/src/gate-demo-iniconfig"
export DEMO_VENV="$HOME/.local/share/gate-demo/iniconfig-venv"
export DEMO_PYTHON="$DEMO_VENV/bin/python"

git clone https://github.com/pytest-dev/iniconfig.git "$DEMO_ROOT"
git -C "$DEMO_ROOT" checkout 77db208ab4ae0cd2061d909fe222a1db72867850
cp "$GATE_ROOT/docs/demo/iniconfig_acceptance_test.py" \
  "$DEMO_ROOT/testing/test_gate_demo_acceptance.py"
git -C "$DEMO_ROOT" add testing/test_gate_demo_acceptance.py
git -C "$DEMO_ROOT" commit -m "demo: add human acceptance test"

python3 -m venv "$DEMO_VENV"
"$DEMO_PYTHON" -m pip install --upgrade pip
"$DEMO_PYTHON" -m pip install -e "$DEMO_ROOT" "pytest>=8.4.2"
```

Use a full clone, not `git clone --depth 1`. The project uses
`setuptools-scm`, which needs repository tags to calculate an installable
version compatible with pytest's `iniconfig>=1` dependency.

Show the protected baseline failing for the intended reason:

```bash
cd "$DEMO_ROOT"
"$DEMO_PYTHON" -I -B -m pytest -q
```

Validated result at the pinned commit: `1 failed, 49 passed`. The new
acceptance test fails with `TypeError: object of type 'IniConfig' has no
len()`; all 49 upstream tests pass.

## Path A: Codex plugin

Install Gate from its source checkout using the same trusted interpreter:

```bash
cd "$GATE_ROOT"
"$DEMO_PYTHON" scripts/install_plugin.py
codex plugin list --marketplace personal
```

Start Codex from the real target repository with the virtual environment first
on `PATH`:

```bash
cd "$DEMO_ROOT"
export PATH="$DEMO_VENV/bin:$PATH"
codex
```

Invoke these in order, replacing the example paths with the absolute values
printed by `printf '%s\n' "$DEMO_PYTHON" "$GATE_ROOT" "$DEMO_ROOT"`:

```text
$gate:doctor Check this repository using the active virtualenv Python.

$gate:run Work in the current repository. Use the task file at /absolute/path/to/gate/docs/demo/iniconfig_task.md and the active virtualenv Python. Report FINAL, AUDIT_LOG, and AUDIT_ROOT exactly.

$gate:audit Verify the absolute AUDIT_LOG path printed by the completed Gate run.
```

The parent task is only the launcher and result viewer. `$gate:run` starts a
separate Gate-controlled child, and only child exit code `0` plus
`FINAL VERIFIED` is success.

## Path B: original standalone CLI

Use this instead of Path A when demonstrating the original CLI. Start from a
fresh prepared clone so two Gate processes never operate on one working tree.
The command shape is `gate.py --repo PROJECT --task TASK_FILE`.

```bash
cd "$DEMO_ROOT"
"$DEMO_PYTHON" "$GATE_ROOT/gate.py" \
  --repo "$DEMO_ROOT" \
  --task "$GATE_ROOT/docs/demo/iniconfig_task.md"
```

After the run, validate the printed audit path:

```bash
"$DEMO_PYTHON" "$GATE_ROOT/verify_chain.py" \
  /absolute/path/from/AUDIT_LOG
```

Both paths execute the same Gate core. The plugin adds discoverability and
external-state setup; it does not redefine verdicts or weaken the standalone
CLI contract.

## Two-minute recording

1. **Before Gate, 20 seconds.** Show the pinned iniconfig project, failing
   acceptance test, then the completed ordinary Codex run. Point out that 50
   tests pass but `GATE_VERDICT`, `AUDIT_LOG`, and `AUDIT_ROOT` are absent.
2. **Original CLI, 20 seconds.** Show the same failing baseline in its clean
   clone, then the CLI's `FINAL VERIFIED`, exact child thread, and audit root.
3. **Plugin setup, 15 seconds.** Show `gate@personal` enabled and invoke
   `$gate:run` from the third clean clone.
4. **Plugin result, 35 seconds.** Speed up waiting time in the edit, but keep
   the exact child thread, verifier output, and terminal verdict readable.
5. **Independent proof, 15 seconds.** Invoke `$gate:audit` and show the matching
   record count and SHA-256 root.
6. **Developer result, 15 seconds.** Show the side-by-side table and close with:
   "Codex can write the change either way. Gate makes completion independently
   verifiable from protected evidence, through a plugin or the original CLI."

The longer recording can retain the original walkthrough below:

1. **Real project, 10 seconds.** Show the iniconfig GitHub page, pinned commit,
   and clean Git history. Say that the feature and acceptance test are demo
   inputs, not an upstream issue.
2. **Protected requirement, 15 seconds.** Open the acceptance test, run the
   isolated pytest command, and show the single expected failure.
3. **Plugin setup, 15 seconds.** Show `gate@personal` enabled, then run
   `$gate:doctor`.
4. **Live work, 55 seconds.** Invoke `$gate:run`. Speed up waiting time in the
   edit, but keep the exact child thread, verifier output, and terminal verdict
   readable. Do not manufacture a retry if the agent solves it in one round.
5. **Independent proof, 15 seconds.** Invoke `$gate:audit` and show the matching
   record count and SHA-256 root.
6. **Developer result, 10 seconds.** Show `git diff` in iniconfig and the full
   green suite. Close with: "Use the plugin inside Codex or the same core from
   the CLI. Gate decides completion from protected evidence."

## Evidence to retain

- Upstream URL and pinned commit.
- Baseline commit containing the human-authored acceptance test.
- Codex parent task and exact Gate child thread IDs.
- Full `FINAL`, `AUDIT_LOG`, and `AUDIT_ROOT` lines.
- Independent `$gate:audit` or `verify_chain.py` output.
- Final iniconfig diff and complete pytest output.

The real-project recording complements the deterministic adversarial fixture.
It demonstrates normal developer adoption; it does not replace the existing
`FALSIFIED -> TAMPERED -> VERIFIED` tamper evidence.
