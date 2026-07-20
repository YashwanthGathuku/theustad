#!/usr/bin/env bash
set -euo pipefail

gate_root="${GATE_ROOT:-$HOME/code/gate}"
demo_home="${DEMO_HOME:-$HOME/code}"
venv_home="${DEMO_VENV_HOME:-$HOME/.local/share/gate-demo}"
gate_repo="https://github.com/YashwanthGathuku/gate.git"
gate_branch="Ash/gate-codex-plugin"
upstream_repo="https://github.com/pytest-dev/iniconfig.git"
upstream_commit="77db208ab4ae0cd2061d909fe222a1db72867850"

mkdir -p "$demo_home" "$venv_home"

if [[ ! -d "$gate_root/.git" ]]; then
  git clone --branch "$gate_branch" --single-branch "$gate_repo" "$gate_root"
fi

acceptance_test="$gate_root/docs/demo/iniconfig_acceptance_test.py"
[[ -f "$acceptance_test" ]] || {
  printf 'Missing acceptance test: %s\n' "$acceptance_test" >&2
  exit 2
}

for mode in no-gate gate-cli gate-plugin; do
  target="$demo_home/iniconfig-$mode"
  venv="$venv_home/$mode-venv"
  python="$venv/bin/python"

  if [[ ! -e "$target" && ! -e "$venv" ]]; then
    git clone "$upstream_repo" "$target"
    git -C "$target" switch --detach "$upstream_commit"
    git -C "$target" switch -c "gate-demo-$mode"
    cp "$acceptance_test" "$target/testing/test_gate_demo_acceptance.py"
    git -C "$target" config user.name "Gate Demo"
    git -C "$target" config user.email "gate-demo@local"
    git -C "$target" add testing/test_gate_demo_acceptance.py
    git -C "$target" commit -m "demo: add human acceptance test"

    python3 -m venv "$venv"
    "$python" -m pip install --upgrade pip
    "$python" -m pip install -e "$target" "pytest>=8.4.2"
  elif [[ ! -d "$target/.git" || ! -x "$python" ]]; then
    printf 'Incomplete demo paths require manual review: %s and %s\n' \
      "$target" "$venv" >&2
    exit 2
  else
    printf 'GATE_DEMO_REUSE %s %s %s\n' "$mode" "$target" "$python"
  fi

  set +e
  baseline="$({ cd "$target" && "$python" -I -B -m pytest -q; } 2>&1)"
  status=$?
  set -e
  printf '%s\n' "$baseline"
  if [[ $status -ne 1 ]] \
    || [[ "$baseline" != *"1 failed, 49 passed"* ]] \
    || [[ "$baseline" != *"object of type 'IniConfig' has no len()"* ]]; then
    printf 'Unexpected %s baseline (exit %s)\n' "$mode" "$status" >&2
    exit 2
  fi
  printf 'GATE_DEMO_BASELINE_OK %s %s %s\n' "$mode" "$target" "$python"
done
