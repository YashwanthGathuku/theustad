# Install and use TheUstad with Codex

TheUstad packages the same `theustad.py` and `theustadlib/` enforcement core
used by the standalone CLI. `$theustad:run` freezes trusted inputs, starts a
separate child Codex task, verifies its final claim, resumes that exact child
with failure evidence when needed, and emits a terminal verdict and audit chain.

## Prerequisites

- Python 3.10 or newer and Git.
- An authenticated Codex CLI.
- Pytest in the trusted Python environment unless an explicit custom verifier
  is configured.
- Linux, macOS, or WSL 2 for `$theustad:doctor` and `$theustad:run`.
- A real Git repository with human-authored acceptance inputs committed before
  TheUstad starts.

Native Windows can install and discover the package and can run
`$theustad:audit` for an existing log. `doctor` and `run` fail closed there
because they require POSIX process-group termination.

## Fresh install

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

The result must show `theustad@personal` with `installed` and `enabled` set to
`true`. Restart Codex after installing or updating the package.

## WSL 2

On a Windows host, keep the TheUstad checkout, trusted environment, and target
repository under the Linux home directory rather than `/mnt/c`:

```powershell
wsl --install -d Ubuntu-24.04
wsl -d Ubuntu-24.04
```

Inside the distribution, install Codex, then use the fresh-install commands:

```bash
sudo apt update
sudo apt install -y git python3-venv bubblewrap curl
curl -fsSL https://chatgpt.com/codex/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
codex login status
```

Start Codex from the Linux project directory with the trusted environment on
`PATH`:

```bash
cd "$HOME/code/my-real-project"
export PATH="$HOME/.local/share/theustad/plugin-venv/bin:$PATH"
codex
```

## Run the skills

In a new Codex task, invoke the skills in order:

```text
$theustad:doctor Check this Git repository using the trusted absolute Python.
$theustad:run Work in the current repository. Use /absolute/path/to/task.md and report CHILD_THREAD, FINAL, AUDIT_LOG, and AUDIT_ROOT exactly.
$theustad:audit Verify the exact absolute AUDIT_LOG path emitted by the completed run.
```

The parent task must not implement the coding task before `$theustad:run`.
Only child exit code `0` and `FINAL VERIFIED` is success; `PASS_NO_CLAIM` is
neutral and is not a successful completion.

## Protected custom verifiers

The default verifier is pytest from the trusted absolute Python. For a project
with a different acceptance command, set an explicit verifier and protect its
inputs before the agent starts:

```bash
python theustad.py --repo /absolute/path/to/project \
  --task /absolute/path/to/task.md \
  --verifier "npm test" \
  --protect-add package.json package-lock.json
```

The custom verifier command is parsed as argv without a shell. A protected
input changed by the agent is restored and reported as `TAMPERED`.

On WSL, custom verifier tools must resolve to WSL-native executables. Check the
real paths for the complete toolchain, such as both `node` and `npm`; a path
under `/mnt/c` points to a Windows installation that may not be able to access
Linux-only repository or state paths. Correct `PATH` or install the Linux
toolchain before running `$theustad:doctor` or `$theustad:run`.

## Upgrade or remove

Update an installed canonical package:

```bash
git -C "$HOME/code/theustad" pull --ff-only
"$HOME/.local/share/theustad/plugin-venv/bin/python" \
  "$HOME/code/theustad/scripts/install_plugin.py"
```

Remove it with:

```bash
codex plugin remove theustad@personal --json
```
