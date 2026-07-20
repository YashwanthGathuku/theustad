#!/usr/bin/env bash
set -uo pipefail

target="${GATE_PLUGIN_REPO:-$HOME/code/iniconfig-gate-plugin}"
python="${GATE_PLUGIN_PYTHON:-$HOME/.local/share/gate-demo/gate-plugin-venv/bin/python}"
gate_root="${GATE_ROOT:-$HOME/code/gate}"
task="${GATE_TASK:-$gate_root/docs/demo/iniconfig_task.md}"
evidence="${DEMO_EVIDENCE:-$HOME/gate-demo-evidence}"
codex="${CODEX_BIN:-$HOME/.local/bin/codex}"
run_id="$(date -u +%Y%m%d_%H%M%S)"
state_home="${GATE_PLUGIN_STATE_HOME:-$HOME/.local/state/gate-demo/plugin-$run_id}"

mkdir -p "$evidence" "$state_home"
cd "$target"
export PATH="$(dirname "$python"):$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
export GATE_STATE_HOME="$state_home"

if [[ -n "$(git status --porcelain)" ]]; then
  printf 'Refusing dirty plugin demo baseline: %s\n' "$target" >&2
  git status --short --branch >&2
  exit 2
fi

"$codex" plugin list --json | tee "$evidence/gate_plugin_list.json"
if ! grep -q '"pluginId": "gate@personal"' "$evidence/gate_plugin_list.json"; then
  printf 'The Gate plugin is not installed.\n' >&2
  exit 2
fi

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set +e
"$python" -I -B -m pytest -q 2>&1 | tee "$evidence/gate_plugin_baseline_tests.txt"
baseline_status=${PIPESTATUS[0]}
if [[ "$baseline_status" -eq 0 ]]; then
  printf 'Expected the human acceptance test to fail before the plugin run.\n' >&2
  exit 2
fi

prompt="Use \$gate:run exactly as installed. Work in the current repository and use the explicit task file at $task with the Python executable $python. Do not edit the target from this parent task. Let Gate launch and control the child coding task. After Gate finishes, use \$gate:audit on the emitted AUDIT_LOG. Report FINAL, AUDIT_LOG, AUDIT_ROOT, child thread ID, and audit validation exactly."
"$codex" exec --json --sandbox danger-full-access "$prompt" \
  2>&1 | tee "$evidence/gate_plugin_console.jsonl"
plugin_status=${PIPESTATUS[0]}

"$python" -I -B -m pytest -q 2>&1 | tee "$evidence/gate_plugin_tests.txt"
test_status=${PIPESTATUS[0]}
set -e

git status --short --branch | tee "$evidence/gate_plugin_git_status.txt"
git diff -- src testing | tee "$evidence/gate_plugin_diff.patch"

audit_log="$(find "$state_home" -type f -name 'audit_*.jsonl' -print | sort | tail -n 1)"
audit_status=2
final_verdict="MISSING"
audit_root="MISSING"
thread_id="MISSING"
if [[ -n "$audit_log" && -f "$audit_log" ]]; then
  set +e
  "$python" "$gate_root/verify_chain.py" "$audit_log" \
    2>&1 | tee "$evidence/gate_plugin_audit.txt"
  audit_status=${PIPESTATUS[0]}
  set -e

  readarray -t audit_fields < <(
    "$python" -c \
      'import json, sys; records=[json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]; session=next(r for r in records if r["kind"] == "session"); final=records[-1]; print(final["data"]["verdict"]); print(final["hash"]); print(session["data"]["thread_id"])' \
      "$audit_log"
  )
  final_verdict="${audit_fields[0]:-MISSING}"
  audit_root="${audit_fields[1]:-MISSING}"
  thread_id="${audit_fields[2]:-MISSING}"
else
  printf 'No plugin audit log was created.\n' | tee "$evidence/gate_plugin_audit.txt"
fi

finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
{
  printf 'MODE gate-codex-plugin\n'
  printf 'STARTED %s\n' "$started"
  printf 'FINISHED %s\n' "$finished"
  printf 'BASELINE_TEST_EXIT %s\n' "$baseline_status"
  printf 'PLUGIN_PARENT_EXIT %s\n' "$plugin_status"
  printf 'INDEPENDENT_TEST_EXIT %s\n' "$test_status"
  printf 'AUDIT_VERIFY_EXIT %s\n' "$audit_status"
  printf 'CHILD_THREAD %s\n' "$thread_id"
  printf 'FINAL %s\n' "$final_verdict"
  printf 'AUDIT_LOG %s\n' "${audit_log:-MISSING}"
  printf 'AUDIT_ROOT %s\n' "$audit_root"
  printf 'STATE_HOME %s\n' "$state_home"
} | tee "$evidence/gate_plugin_summary.txt"

if [[ "$plugin_status" -ne 0 || "$test_status" -ne 0 || "$audit_status" -ne 0 || "$final_verdict" != "VERIFIED" ]]; then
  exit 1
fi
