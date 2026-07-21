# Install and use TheUstad with Codex

TheUstad adds protected verification to a Codex coding task. The parent Codex
task invokes `$theustad:run`; TheUstad freezes trusted inputs, starts a separate child Codex
task, runs the verifier, resumes that exact child with failure evidence when
needed, and emits a terminal verdict plus a portable audit chain.

The plugin and standalone CLI use the same `theustad.py` and `theustadlib/` core.

## Prerequisites

- Python 3.10 or newer.
- Pytest installed in the trusted Python environment, unless an explicit
  custom verifier is used.
- Git and an authenticated Codex CLI.
- Linux, macOS, or WSL 2 for `$theustad:doctor` and `$theustad:run`.
- A real Git repository with the acceptance tests committed before TheUstad starts.

Native Windows cannot provide TheUstad's required POSIX process-group termination.
The plugin can be installed and discovered there, and `$theustad:audit` can verify
an existing log, but coding runs fail closed. Use the WSL 2 workflow below.

## Install the plugin

Clone TheUstad and create a trusted environment outside any target repository:

```bash
git clone https://github.com/YashwanthGathuku/theustad.git
cd theustad

python3 -m venv "$HOME/.local/share/theustad/plugin-venv"
THEUSTAD_PYTHON="$HOME/.local/share/theustad/plugin-venv/bin/python"
"$THEUSTAD_PYTHON" -m pip install --upgrade pip pytest
"$THEUSTAD_PYTHON" scripts/install_plugin.py
codex plugin list --json
```

The final command must show `theustad@personal` with `installed` and `enabled` set
to `true`. The installer:

1. Copies an allowlisted package to `~/plugins/theustad`.
2. Adds or updates TheUstad in `~/.agents/plugins/marketplace.json` without
   replacing unrelated plugins.
3. Runs `codex plugin add theustad@personal --json` without a shell.

Restart Codex after first installation or after an update so a new task loads
the current skill bundle.

## Use TheUstad in the Codex UI

On Linux or macOS, open the real project in Codex Desktop. On WSL 2, start the
Codex terminal UI from the Linux project directory with the trusted virtual
environment first on `PATH`:

```bash
cd "$HOME/code/my-real-project"
export PATH="$HOME/.local/share/theustad/plugin-venv/bin:$PATH"
codex
```

In a new Codex task, invoke the skills in this order:

```text
$theustad:doctor Check this Git repository using
/home/me/.local/share/theustad/plugin-venv/bin/python.

$theustad:run Work in the current repository. Use the explicit task file at
/home/me/code/my-real-project/task.md and the trusted Python at
/home/me/.local/share/theustad/plugin-venv/bin/python. Report CHILD_THREAD,
FINAL, AUDIT_LOG, and AUDIT_ROOT exactly.

$theustad:audit Verify the exact absolute AUDIT_LOG path emitted by the completed
TheUstad run. Report the validator output and exit code exactly.
```

The UI task is a launcher and result viewer. It must not implement the coding
task before `$theustad:run`; TheUstad owns the separate child task. Success requires
both child exit code `0` and `FINAL VERIFIED`. `PASS_NO_CLAIM` is neutral, not
success.

## Windows with WSL 2

Keep the working repository under the Linux home directory, not under
`/mnt/c`, then install and run TheUstad inside the same distribution:

```powershell
wsl --install -d Ubuntu-24.04
wsl -d Ubuntu-24.04
```

Inside Ubuntu:

```bash
sudo apt update
sudo apt install -y git python3-venv bubblewrap curl
curl -fsSL https://chatgpt.com/codex/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
codex login status

git clone https://github.com/YashwanthGathuku/theustad.git "$HOME/code/theustad"
cd "$HOME/code/theustad"
python3 -m venv "$HOME/.local/share/theustad/plugin-venv"
THEUSTAD_PYTHON="$HOME/.local/share/theustad/plugin-venv/bin/python"
"$THEUSTAD_PYTHON" -m pip install --upgrade pip pytest
"$THEUSTAD_PYTHON" scripts/install_plugin.py

cd "$HOME/code/my-real-project"
export PATH="$HOME/.local/share/theustad/plugin-venv/bin:$HOME/.local/bin:$PATH"
codex
```

The native Windows Codex Desktop may display the personal plugin, but do not
present a native `$theustad:run` as supported. The successful Windows-hosted demo
runs in the WSL 2 Codex terminal UI.

## Use the standalone CLI

The original CLI is useful for automation, direct security review, and users
who do not install personal plugins:

```bash
THEUSTAD_ROOT="$HOME/code/theustad"
PROJECT="$HOME/code/my-real-project"
PYTHON="$HOME/.local/share/theustad/plugin-venv/bin/python"

"$PYTHON" "$THEUSTAD_ROOT/theustad.py" \
  --repo "$PROJECT" \
  --task "$PROJECT/task.md" \
  --state-dir "$HOME/.local/state/theustad/manual-run" \
  --log "$HOME/.local/state/theustad/manual-run/logs" \
  --no-color
```

Validate the printed log independently:

```bash
"$PYTHON" "$THEUSTAD_ROOT/verify_chain.py" \
  /absolute/path/from/AUDIT_LOG
```

## Apply TheUstad to a real project

1. Commit or otherwise cleanly establish the project baseline.
2. Add and commit human-authored acceptance tests before TheUstad starts.
3. Put the task contract in a file such as `task.md`.
4. Keep the trusted Python environment and TheUstad state outside the repository.
5. Run `$theustad:doctor`, then `$theustad:run`, then `$theustad:audit`.
6. Review the production diff and full verifier output even after `VERIFIED`.
7. Anchor `AUDIT_ROOT` outside the log, such as in a pushed commit or release
   record, when later tamper detection matters.

The permanent iniconfig comparison under
[`docs/evidence/real_project_demo`](evidence/real_project_demo/README.md)
shows ordinary Codex, the standalone CLI, and the installed plugin against the
same pinned real project.

## Update or remove

Re-run the installer from a newer TheUstad checkout, then restart Codex:

```bash
git -C "$HOME/code/theustad" pull --ff-only
"$HOME/.local/share/theustad/plugin-venv/bin/python" \
  "$HOME/code/theustad/scripts/install_plugin.py"
```

Remove TheUstad from Codex with:

```bash
codex plugin remove theustad@personal --json
```

## Troubleshooting

- `THEUSTAD_PLUGIN_ERROR ... Python ... pytest`: use the external virtualenv's
  absolute Python path and ensure pytest is installed there.
- `TheUstad requires Linux, macOS, or WSL 2`: move the run into WSL 2; do not
  disable the fail-closed check.
- Skill not visible: restart Codex and confirm `codex plugin list --json` shows
  `theustad@personal` enabled.
- `Not inside a trusted directory`: run from the real Git repository. Do not
  bypass repository checks for a production TheUstad run.
- `FINAL` is not `VERIFIED`: treat the run as non-success and inspect the exact
  verdict, verifier evidence, and audit log.

## Gate 1.x compatibility

Gate-named entry points are deprecated adapters through TheUstad 1.x. Existing
automation may temporarily use `gate.py`, `gatelib`, `GATE_STATE_HOME`,
`GATE_PYTHON`, `gate@personal`, and `$gate:*`; canonical TheUstad names take
precedence whenever both forms are configured. To install the optional plugin
adapter explicitly, run:

```bash
"$THEUSTAD_PYTHON" scripts/install_plugin.py --install-legacy-alias
```

The compatibility package forwards to `theustad.py`, `theustadlib`, and the
`theustad@personal` launcher. It contains no second verification runtime and is
scheduled for removal in 2.0.
