#!/usr/bin/env bash
set -uo pipefail

target="${NO_GATE_REPO:-$HOME/code/iniconfig-no-gate}"
python="${NO_GATE_PYTHON:-$HOME/.local/share/gate-demo/no-gate-venv/bin/python}"
task="${GATE_TASK:-$HOME/code/gate/docs/demo/iniconfig_task.md}"
evidence="${DEMO_EVIDENCE:-$HOME/gate-demo-evidence}"
codex="${CODEX_BIN:-$HOME/.local/bin/codex}"

mkdir -p "$evidence"
cd "$target"
export PATH="$(dirname "$python"):$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

if "$codex" plugin list --json | grep -q '"pluginId": "gate@personal"'; then
  printf 'Remove gate@personal before recording the no-Gate comparison.\n' >&2
  exit 2
fi

if [[ -n "$(git status --porcelain)" ]]; then
  printf 'Refusing dirty no-Gate demo baseline: %s\n' "$target" >&2
  git status --short --branch >&2
  exit 2
fi

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set +e
"$codex" exec --json --sandbox workspace-write \
  "Work as ordinary Codex without Gate. Read and implement the task at $task in the current repository. Do not invoke any Gate skill, Gate launcher, or gate.py. Run the complete test suite and report what you changed and verified." \
  2>&1 | tee "$evidence/no_gate_console.jsonl"
codex_status=${PIPESTATUS[0]}

"$python" -I -B -m pytest -q 2>&1 | tee "$evidence/no_gate_tests.txt"
test_status=${PIPESTATUS[0]}
set -e

git status --short --branch | tee "$evidence/no_gate_git_status.txt"
git diff -- src testing | tee "$evidence/no_gate_diff.patch"
finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

{
  printf 'MODE ordinary-codex-without-gate\n'
  printf 'STARTED %s\n' "$started"
  printf 'FINISHED %s\n' "$finished"
  printf 'CODEX_EXIT %s\n' "$codex_status"
  printf 'INDEPENDENT_TEST_EXIT %s\n' "$test_status"
  printf 'GATE_VERDICT NONE\n'
  printf 'AUDIT_LOG NONE\n'
  printf 'AUDIT_ROOT NONE\n'
} | tee "$evidence/no_gate_summary.txt"

exit "$test_status"
