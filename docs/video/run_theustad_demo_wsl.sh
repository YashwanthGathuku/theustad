#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
theustad_root="${THEUSTAD_ROOT:-$(cd -- "$script_dir/../.." && pwd)}"
evidence_root="${DEMO_EVIDENCE:-$HOME/theustad-live-demo-evidence}"
plugin_repo="${THEUSTAD_PLUGIN_REPO:-$HOME/theustad-demo-code/iniconfig-theustad-plugin}"
plugin_python="${THEUSTAD_PLUGIN_PYTHON:-$HOME/.local/share/theustad-demo/theustad-plugin-venv/bin/python}"
codex="${CODEX_BIN:-$HOME/.local/bin/codex}"
task="$theustad_root/docs/demo/iniconfig_task.md"
markers="${VIDEO_MARKERS:-$evidence_root/markers.txt}"
done_file="${VIDEO_DONE:-$evidence_root/recording.done}"
status_file="${VIDEO_STATUS:-$evidence_root/recording.status}"
committed_evidence="$theustad_root/docs/evidence/theustad-1.0"

mkdir -p "$evidence_root" "$(dirname -- "$markers")" "$(dirname -- "$done_file")" \
  "$(dirname -- "$status_file")"
: > "$markers"
rm -f "$done_file" "$status_file"

finish() {
  local status=$?
  trap - EXIT
  printf '%s\n' "$status" > "$status_file"
  touch "$done_file"
  exit "$status"
}
trap finish EXIT

export PATH="$(dirname -- "$plugin_python"):$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

mark() {
  printf '%s %s\n' "$(date +%s)" "$1" | tee -a "$markers"
}

screen() {
  printf '\033c'
  printf '\n  THEUSTAD 1.0 - CODING CLAIMS NEED PROOF\n'
  printf '  ======================================\n\n%s\n\n' "$1"
}

require_file() {
  test -f "$1" || { printf 'Missing committed evidence: %s\n' "$1" >&2; exit 2; }
}

mark intro
screen "TheUstad turns an agent's done message into a falsifiable claim."
printf '  Eight scenes: control, install, one fresh plugin run, restoration, and audit.\n'
printf '  This recording is a raw desktop capture; narration is added separately.\n'
sleep 2

mark control
screen "WITHOUT THEUSTAD - CAPTURED REAL CONTROL RUN"
require_file "$committed_evidence/real-project/no_theustad_summary.txt"
cat "$committed_evidence/real-project/no_theustad_summary.txt"
printf '\n  The ordinary Codex run solved the pinned task, but reported no protected verdict or audit root.\n'
sleep 3

mark install
screen "INSTALL - ONE THEUSTAD CODEX PLUGIN"
require_file "$committed_evidence/plugin_list.json"
cat "$committed_evidence/plugin_list.json"
printf '\n  The committed installation evidence names theustad@personal and its three skills.\n'
sleep 3

mark plugin_start
screen "WITH THEUSTAD - ONE FRESH REAL PLUGIN RUN"
printf '  $theustad:run is sent through codex exec against the clean plugin clone.\n\n'
THEUSTAD_ROOT="$theustad_root" \
THEUSTAD_PLUGIN_REPO="$plugin_repo" \
THEUSTAD_PLUGIN_PYTHON="$plugin_python" \
THEUSTAD_TASK="$task" \
THEUSTAD_STATE_HOME="${THEUSTAD_STATE_HOME:-$HOME/.local/state/theustad-live-demo}" \
DEMO_EVIDENCE="$evidence_root" \
CODEX_BIN="$codex" \
bash "$theustad_root/docs/demo/run_theustad_plugin_wsl.sh"

mark plugin_result
screen "WITH THEUSTAD - PROTECTED DECISION"
require_file "$evidence_root/theustad_plugin_summary.txt"
cat "$evidence_root/theustad_plugin_summary.txt"
printf '\n  This is one fresh real plugin execution, not a replay of committed console text.\n'
sleep 3

mark tamper
screen "DETERMINISTIC REHEARSAL - A2 CONFTEST POISONING"
printf '  Scripted adversarial rehearsal: the protected conftest.py is planted, detected, and removed.\n\n'
a2_root="$(mktemp -d "${TMPDIR:-/tmp}/theustad-a2.XXXXXX")"
a2_repo="$a2_root/repo"
a2_state="$a2_root/state"
a2_log="$a2_root/log"
mkdir -p "$a2_state" "$a2_log"
"$plugin_python" -I -B "$theustad_root/fake_codex.py" reset --repo "$a2_repo"
agent_cmd="$plugin_python $theustad_root/fake_codex.py conftest_poison"
resume_cmd="$plugin_python $theustad_root/fake_codex.py conftest_poison --resume '{thread_id}'"
set +e
"$plugin_python" "$theustad_root/theustad.py" \
  --repo "$a2_repo" --task "$task" --cmd "$agent_cmd" --resume-cmd "$resume_cmd" \
  --state-dir "$a2_state" --log "$a2_log" --max-retries 0 --timeout 30 --no-color \
  2>&1 | tee "$evidence_root/a2-live.txt"
a2_status=${PIPESTATUS[0]}
set -e
test "$a2_status" -ne 0
grep -q 'FINAL TAMPERED' "$evidence_root/a2-live.txt"
test ! -e "$a2_repo/conftest.py"
printf '\n  A2 result: TAMPERED; restoration proof: conftest.py is absent after the run.\n'
rm -rf "$a2_root"
sleep 3

mark audit
screen "AUDIT - COPIED RECORD BROKEN, ORIGINAL VALID"
broken_log="$committed_evidence/robustness/b4-tampered-copy.jsonl"
valid_log="$committed_evidence/robustness/b3-1-audit.jsonl"
require_file "$broken_log"
require_file "$valid_log"
set +e
"$plugin_python" -I -B "$theustad_root/verify_chain.py" "$broken_log" 2>&1 | tee "$evidence_root/b4-broken.txt"
broken_status=${PIPESTATUS[0]}
"$plugin_python" -I -B "$theustad_root/verify_chain.py" "$valid_log" 2>&1 | tee "$evidence_root/b4-valid.txt"
valid_status=${PIPESTATUS[0]}
set -e
test "$broken_status" -ne 0
test "$valid_status" -eq 0
grep -q '^BROKEN' "$evidence_root/b4-broken.txt"
grep -q '^VALID:' "$evidence_root/b4-valid.txt"
printf '\n  BROKEN is the edited copy. VALID is the untouched SHA-256 chain.\n'
sleep 3

mark closing
screen "THEUSTAD - CLAIMS NEED PROOF"
printf '  Ordinary Codex can produce working code. TheUstad adds protected inputs,\n'
printf '  an exact child task, restoration evidence, and an independently valid audit root.\n\n'
printf '  Recording complete. No raw audio is required for this capture.\n'
sleep 3
