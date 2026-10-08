#!/usr/bin/env bash
# Runs TheUstad's CI check for the composite GitHub Action in action.yml.
#
# Inputs arrive as environment variables and are only ever expanded inside
# double quotes, so a branch name, a pull request title or an input value
# cannot become shell syntax here.
set -euo pipefail

base="${THEUSTAD_BASE:-}"
if [ -z "$base" ]; then
  echo "::error title=TheUstad::no base commit. On pull_request events it defaults to the pull request's base; on other events set the 'base' input." >&2
  exit 2
fi

python="${THEUSTAD_PYTHON:-python3}"
action_path="${GITHUB_ACTION_PATH:?GITHUB_ACTION_PATH is not set}"
workspace="${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is not set}"
state="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/theustad-ci"
result="$state/result.json"
mkdir -p "$state"
rm -f "$result"

args=(ci --repo "$workspace" --base "$base" --ephemeral --state-dir "$state" --json "$result")
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  args+=(--summary "$GITHUB_STEP_SUMMARY")
fi
if [ -n "${THEUSTAD_VERIFIER:-}" ]; then
  args+=(--verifier "$THEUSTAD_VERIFIER")
fi
if [ -n "${THEUSTAD_PROTECT_ADD:-}" ]; then
  read -r -a extra <<< "$THEUSTAD_PROTECT_ADD"
  args+=(--protect-add "${extra[@]}")
fi
if [ "${THEUSTAD_CENSUS:-true}" = "false" ]; then
  args+=(--no-census)
fi
if [ -n "${THEUSTAD_TIMEOUT:-}" ]; then
  args+=(--timeout "$THEUSTAD_TIMEOUT")
fi

status=0
"$python" "$action_path/theustad.py" "${args[@]}" || status=$?

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  verdict="ERROR"
  audit_log=""
  if [ -f "$result" ]; then
    read_field='import json, sys; data = json.load(open(sys.argv[1], encoding="utf-8")); value = data[sys.argv[2]]; print((value.get(sys.argv[3]) if sys.argv[3] else value) or "")'
    verdict="$("$python" -c "$read_field" "$result" verdict "")"
    audit_log="$("$python" -c "$read_field" "$result" audit log)"
  fi
  {
    echo "verdict=$verdict"
    echo "audit-log=$audit_log"
    echo "result=$result"
  } >> "$GITHUB_OUTPUT"
fi
exit "$status"
