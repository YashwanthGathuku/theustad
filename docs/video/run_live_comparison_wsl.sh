#!/usr/bin/env bash
set -euo pipefail

gate_root="${GATE_ROOT:-$HOME/code/gate}"
harness_root="${HARNESS_ROOT:-/mnt/c/Users/Gathu/Projects/gate/.worktrees/gate-codex-plugin}"
demo_home="${DEMO_HOME:-$HOME/gate-video-code}"
venv_home="${DEMO_VENV_HOME:-$HOME/.local/share/gate-video-demo}"
evidence="${DEMO_EVIDENCE:-$HOME/gate-video-recording-evidence}"
markers="${VIDEO_MARKERS:-$evidence/markers.txt}"
done_file="${VIDEO_DONE:-$evidence/recording.done}"
status_file="${VIDEO_STATUS:-$evidence/recording.status}"

no_gate_repo="$demo_home/iniconfig-no-gate"
plugin_repo="$demo_home/iniconfig-gate-plugin"
no_gate_python="$venv_home/no-gate-venv/bin/python"
plugin_python="$venv_home/gate-plugin-venv/bin/python"

mkdir -p "$evidence" "$(dirname "$markers")" "$(dirname "$done_file")" \
  "$(dirname "$status_file")"
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
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

mark() {
  printf '%s %s\n' "$(date +%s)" "$1" | tee -a "$markers" >/dev/null
}

screen() {
  printf '\033c'
  printf '\n  GATE v2 - LIVE REAL-PROJECT PROOF\n'
  printf '  =================================\n\n'
  printf '%s\n' "$1"
  printf '\n'
}

require_clean() {
  local repo="$1"
  if [[ -n "$(git -C "$repo" status --porcelain)" ]]; then
    printf 'Recording target is dirty: %s\n' "$repo" >&2
    git -C "$repo" status --short >&2
    exit 2
  fi
}

require_clean "$no_gate_repo"
require_clean "$plugin_repo"
test -f "$harness_root/docs/demo/run_no_gate_wsl.sh"
test -f "$harness_root/docs/demo/run_gate_plugin_wsl.sh"

mark intro
screen "REAL PROJECT: pytest-dev/iniconfig @ 77db208ab4ae0cd2061d909fe222a1db72867850"
printf '  Same committed human acceptance test in both clean clones.\n'
printf '  Baseline in each clone: 1 failed, 49 passed.\n\n'
printf '  Task: add __len__ to IniConfig and SectionWrapper.\n'
printf '  First run: ordinary Codex, with Gate unavailable.\n'
printf '  Second run: installed Codex plugin using \$gate:run and \$gate:audit.\n'
sleep 7

mark no_gate_start
screen "WITHOUT GATE - ordinary Codex controls its own edit and test loop"
printf '  Removing gate@personal before the run:\n'
printf '    codex plugin remove gate@personal --json\n\n'
codex plugin remove gate@personal --json || true
printf '\n  Launching the ordinary coding task now.\n'
sleep 3

NO_GATE_REPO="$no_gate_repo" \
NO_GATE_PYTHON="$no_gate_python" \
GATE_ROOT="$gate_root" \
GATE_TASK="$gate_root/docs/demo/iniconfig_task.md" \
DEMO_EVIDENCE="$evidence" \
CODEX_BIN="$HOME/.local/bin/codex" \
bash "$harness_root/docs/demo/run_no_gate_wsl.sh"

mark no_gate_summary
screen "WITHOUT GATE - code works, but completion is self-reported"
cat "$evidence/no_gate_summary.txt"
printf '\nIndependent project tests:\n'
cat "$evidence/no_gate_tests.txt"
printf '\nWhat is missing: protected snapshot, Gate verdict, audit log, audit root.\n'
printf 'This is the control result. Ordinary Codex solved the task.\n'
sleep 10

mark plugin_install
screen "INSTALL GATE - one personal Codex plugin, three named skills"
printf '  Trusted Python: %s\n\n' "$plugin_python"
printf '  $ %s %s/scripts/install_plugin.py\n' "$plugin_python" "$gate_root"
"$plugin_python" "$gate_root/scripts/install_plugin.py"
printf '\n  $ codex plugin list --json\n'
codex plugin list --json
printf '\n  Codex skills: \$gate:doctor  \$gate:run  \$gate:audit\n'
sleep 9

mark plugin_start
screen "WITH GATE - the Codex UI task delegates to a protected child"
printf '  UI prompt:\n'
printf '    \$gate:run Use the committed task file and trusted Python.\n'
printf '    Report CHILD_THREAD, FINAL, AUDIT_LOG, and AUDIT_ROOT exactly.\n\n'
printf '  Gate freezes protected evidence before child Codex starts.\n'
sleep 4

GATE_PLUGIN_REPO="$plugin_repo" \
GATE_PLUGIN_PYTHON="$plugin_python" \
GATE_PLUGIN_STATE_HOME="$HOME/.local/state/gate-video-recording" \
GATE_ROOT="$gate_root" \
GATE_TASK="$gate_root/docs/demo/iniconfig_task.md" \
DEMO_EVIDENCE="$evidence" \
CODEX_BIN="$HOME/.local/bin/codex" \
bash "$harness_root/docs/demo/run_gate_plugin_wsl.sh"

mark plugin_summary
screen "WITH GATE - independent protected verification"
cat "$evidence/gate_plugin_summary.txt"
printf '\nIndependent audit validation:\n'
cat "$evidence/gate_plugin_audit.txt"
printf '\nThe code result is green in both runs. Gate adds the trustworthy decision.\n'
sleep 12

mark comparison
screen "BEFORE / AFTER"
printf '  WITHOUT GATE                         WITH GATE PLUGIN\n'
printf '  ------------                         ----------------\n'
printf '  Project tests pass                   Project tests pass\n'
printf '  Agent reports completion             FINAL VERIFIED\n'
printf '  No protected snapshot                Tests/config frozen externally\n'
printf '  No exact Gate child                  Exact child thread recorded\n'
printf '  No audit log or root                 Valid SHA-256 audit + root\n\n'
printf '  Original CLI uses the same core:\n'
printf '    python gate.py --repo PROJECT --task TASK.md\n\n'
printf '  Full install and Codex UI guide: docs/PLUGIN_GUIDE.md\n'
sleep 12

mark done
