#!/usr/bin/env bash
# Runs TheUstad's CI check for the composite GitHub Action in action.yml.
#
# Inputs arrive as environment variables and are only ever expanded inside
# double quotes, so a branch name, a pull request title or an input value
# cannot become shell syntax here.
set -euo pipefail

python="${THEUSTAD_PYTHON:-python3}"
action_path="${GITHUB_ACTION_PATH:?GITHUB_ACTION_PATH is not set}"
workspace="${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is not set}"

base="${THEUSTAD_BASE:-}"
event_base="${THEUSTAD_EVENT_BASE:-}"
event_head="${THEUSTAD_EVENT_HEAD:-}"
event_sha="${THEUSTAD_EVENT_SHA:-}"
if [ -n "$event_base" ]; then
  # On a pull request GitHub runs the pull request's own workflow, so what
  # that workflow says to compare against is part of the change under
  # review: `base: HEAD` would make the change its own baseline. The event's
  # base and revisions come from GitHub, not from the workflow.
  if [ -n "$base" ] && [ "$base" != "$event_base" ]; then
    echo "::warning title=TheUstad::ignoring the 'base' input on a pull request; comparing against the pull request's base commit $event_base" >&2
  fi
  base="$event_base"
  # Judge exactly the revision GitHub attaches this check to: its merge
  # commit, or the pull request's head. A step before this one could
  # otherwise commit, or just write, a passing tree on top and have that
  # judged instead.
  checked_out="$(git -C "$workspace" rev-parse HEAD 2>/dev/null || true)"
  if [ -z "$checked_out" ] || { [ "$checked_out" != "$event_sha" ] && [ "$checked_out" != "$event_head" ]; }; then
    echo "::error title=TheUstad::the checkout is at ${checked_out:-no commit}, which is neither the pull request's merge commit $event_sha nor its head $event_head. Check out the pull request (actions/checkout's default) and commit nothing before this step." >&2
    exit 2
  fi
  if [ -n "$(git -C "$workspace" status --porcelain --untracked-files=no)" ]; then
    echo "::error title=TheUstad::tracked files differ from the pull request's commit, so a step before this one changed the code TheUstad would judge." >&2
    exit 2
  fi
fi
if [ -z "$base" ]; then
  echo "::error title=TheUstad::no base commit. On pull_request events it is the pull request's base; on other events set the 'base' input." >&2
  exit 2
fi
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
