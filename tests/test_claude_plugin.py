"""The Claude Code plugin: what it declares, and that what it declares works."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from theustadlib import claudesettings


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
MARKETPLACE = json.loads(
    (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
)


def test_marketplace_lists_this_repository_as_the_plugin():
    [entry] = MARKETPLACE["plugins"]

    assert MARKETPLACE["name"] == "theustad"
    assert entry["name"] == PLUGIN["name"] == "theustad"
    assert entry["source"] == "./"


def test_codex_skills_are_not_loaded_into_claude_code():
    # Listing skills in the entry replaces the default skills/ scan, which
    # would otherwise load the Codex plugin's skills into every session.
    [entry] = MARKETPLACE["plugins"]

    assert entry["skills"] == ["./claude-code/skills/"]
    skills = sorted(path.parent.name for path in (ROOT / "claude-code" / "skills").glob("*/SKILL.md"))
    assert skills == ["status"]


def test_status_skill_is_read_only_and_says_so():
    skill = (ROOT / "claude-code" / "skills" / "status" / "SKILL.md").read_text(encoding="utf-8")

    assert skill.startswith("---\nname: status\n")
    assert "status --repo" in skill
    assert "Do not run `enroll`" in skill


@pytest.mark.parametrize("event", claudesettings.HOOK_EVENTS)
def test_declared_hooks_route_through_the_plugin_vendor(event):
    [group] = PLUGIN["hooks"][event]
    [handler] = group["hooks"]

    assert set(PLUGIN["hooks"]) == set(claudesettings.HOOK_EVENTS)
    assert handler["type"] == "command"
    assert handler["args"] == [
        "${CLAUDE_PLUGIN_ROOT}/theustad.py",
        "hook",
        claudesettings.PLUGIN_VENDOR,
        event,
    ]
    assert handler["timeout"] == claudesettings.HANDLER_TIMEOUT


def _declared_hook(event, tmp_path, payload):
    """Run a hook the way the manifest declares it.

    The manifest names ``python3``; the test substitutes this interpreter so
    it runs wherever the suite does.
    """
    [group] = PLUGIN["hooks"][event]
    [handler] = group["hooks"]
    args = [arg.replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT)) for arg in handler["args"]]
    return subprocess.run(
        [sys.executable, *args],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CLAUDE_PLUGIN_ROOT": str(ROOT),
            "THEUSTAD_HOME": str(tmp_path / "external"),
        },
        check=False,
    )


def _payloads(repo):
    common = {"session_id": "plugin-e2e", "transcript_path": "/tmp/t.jsonl", "cwd": str(repo)}
    start = {**common, "hook_event_name": "SessionStart", "source": "startup"}
    stop = {
        **common,
        "permission_mode": "default",
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "last_assistant_message": "Done, and all tests pass.",
        "background_tasks": [],
        "session_crons": [],
    }
    return start, stop


def test_declared_hooks_verify_and_block_a_real_session(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_guard.py").write_text("def test_guard():\n    assert True\n")
    (repo / "pytest.ini").write_text("[pytest]\n")
    enrolled = subprocess.run(
        [sys.executable, str(ROOT / "theustad.py"), "enroll", "--repo", str(repo), "--no-census"],
        capture_output=True,
        text=True,
        env={**os.environ, "THEUSTAD_HOME": str(tmp_path / "external")},
        check=False,
    )
    assert enrolled.returncode == 0, enrolled.stderr
    start, stop = _payloads(repo)

    assert _declared_hook("SessionStart", tmp_path, start).returncode == 0
    green = _declared_hook("Stop", tmp_path, stop)
    assert green.returncode == 0, green.stderr
    assert "VERIFIED" in green.stdout

    (repo / "tests" / "test_guard.py").unlink()
    tampered = _declared_hook("Stop", tmp_path, stop)
    assert tampered.returncode == 2
    assert (repo / "tests" / "test_guard.py").is_file()


@pytest.mark.skipif(shutil.which("claude") is None, reason="Claude Code CLI not installed")
def test_claude_code_accepts_the_manifests():
    for manifest in ("marketplace.json", "plugin.json"):
        completed = subprocess.run(
            ["claude", "plugin", "validate", str(ROOT / ".claude-plugin" / manifest)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "Validation passed" in completed.stdout
