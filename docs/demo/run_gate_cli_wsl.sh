#!/usr/bin/env bash
set -uo pipefail

target="${GATE_CLI_REPO:-$HOME/code/iniconfig-gate-cli}"
python="${GATE_CLI_PYTHON:-$HOME/.local/share/gate-demo/gate-cli-venv/bin/python}"
gate_root="${GATE_ROOT:-$HOME/code/gate}"
task="${GATE_TASK:-$gate_root/docs/demo/iniconfig_task.md}"
evidence="${DEMO_EVIDENCE:-$HOME/gate-demo-evidence}"
run_id="$(date -u +%Y%m%d_%H%M%S)"
state="${GATE_CLI_STATE:-$HOME/.local/state/gate-demo/cli-$run_id}"

mkdir -p "$evidence" "$state"
cd "$target"
export PATH="$(dirname "$python"):$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

if [[ -n "$(git status --porcelain)" ]]; then
  printf 'Refusing dirty CLI demo baseline: %s\n' "$target" >&2
  git status --short --branch >&2
  exit 2
fi

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set +e
"$python" -I -B -m pytest -q 2>&1 | tee "$evidence/gate_cli_baseline_tests.txt"
baseline_status=${PIPESTATUS[0]}
if [[ "$baseline_status" -eq 0 ]]; then
  printf 'Expected the human acceptance test to fail before Gate.\n' >&2
  exit 2
fi

"$python" "$gate_root/gate.py" \
  --repo "$target" \
  --task "$task" \
  --state-dir "$state" \
  --log "$state/logs" \
  --no-color \
  2>&1 | tee "$evidence/gate_cli_console.txt"
gate_status=${PIPESTATUS[0]}

"$python" -I -B -m pytest -q 2>&1 | tee "$evidence/gate_cli_tests.txt"
test_status=${PIPESTATUS[0]}
set -e

git status --short --branch | tee "$evidence/gate_cli_git_status.txt"
git diff -- src testing | tee "$evidence/gate_cli_diff.patch"

final_line="$(grep '^FINAL ' "$evidence/gate_cli_console.txt" | tail -n 1 || true)"
audit_log="$(sed -n 's/^AUDIT_LOG //p' "$evidence/gate_cli_console.txt" | tail -n 1)"
audit_root="$(sed -n 's/^AUDIT_ROOT //p' "$evidence/gate_cli_console.txt" | tail -n 1)"
thread_id="$(sed -n \
  's/.*"type":"thread.started","thread_id":"\([^"]*\)".*/\1/p; s/^CHILD_THREAD //p; s/^THREAD_ID //p' \
  "$evidence/gate_cli_console.txt" | tail -n 1)"

audit_status=2
if [[ -n "$audit_log" && -f "$audit_log" ]]; then
  set +e
  "$python" "$gate_root/verify_chain.py" "$audit_log" \
    2>&1 | tee "$evidence/gate_cli_audit.txt"
  audit_status=${PIPESTATUS[0]}
  set -e
else
  printf 'No readable AUDIT_LOG was emitted.\n' | tee "$evidence/gate_cli_audit.txt"
fi

finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
{
  printf 'MODE gate-standalone-cli\n'
  printf 'STARTED %s\n' "$started"
  printf 'FINISHED %s\n' "$finished"
  printf 'BASELINE_TEST_EXIT %s\n' "$baseline_status"
  printf 'GATE_EXIT %s\n' "$gate_status"
  printf 'INDEPENDENT_TEST_EXIT %s\n' "$test_status"
  printf 'AUDIT_VERIFY_EXIT %s\n' "$audit_status"
  printf 'CHILD_THREAD %s\n' "${thread_id:-SEE_CONSOLE}"
  printf '%s\n' "${final_line:-FINAL MISSING}"
  printf 'AUDIT_LOG %s\n' "${audit_log:-MISSING}"
  printf 'AUDIT_ROOT %s\n' "${audit_root:-MISSING}"
  printf 'STATE_DIR %s\n' "$state"
} | tee "$evidence/gate_cli_summary.txt"

if [[ "$gate_status" -ne 0 || "$test_status" -ne 0 || "$audit_status" -ne 0 ]]; then
  exit 1
fi
