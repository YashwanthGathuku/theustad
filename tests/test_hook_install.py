"""Installing TheUstad's Claude Code hooks into user settings."""

import io
import json
import os
import shlex
import sys
from pathlib import Path

import pytest

import theustad
from theustadlib import claudesettings, enrollment, hookadapter


def settings_file():
    return claudesettings.user_settings_path()


def our_commands(settings):
    return {
        event: [handler["command"] for handler in handlers]
        for event, handlers in claudesettings.installed_handlers(settings).items()
    }


def _repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_ok.py").write_text("def test_ok(): assert True\n")
    return repo


def test_install_creates_both_hooks_with_absolute_paths(capsys):
    assert theustad.main(["install-hooks"]) == 0

    settings = json.loads(settings_file().read_text(encoding="utf-8"))
    handlers = claudesettings.installed_handlers(settings)
    assert set(handlers) == {"SessionStart", "Stop"}
    for event, [handler] in handlers.items():
        argv = shlex.split(handler["command"])
        assert Path(argv[0]).is_absolute() and Path(argv[1]).is_absolute()
        assert argv[-3:] == ["hook", "claude", event]
        assert handler["timeout"] == claudesettings.HANDLER_TIMEOUT
    assert "INSTALLED" in capsys.readouterr().out


def test_install_is_idempotent():
    theustad.main(["install-hooks"])
    first = settings_file().read_text(encoding="utf-8")
    theustad.main(["install-hooks"])

    assert settings_file().read_text(encoding="utf-8") == first


def test_install_keeps_everything_that_is_not_ours():
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    original = {
        "model": "keep-me",
        "hooks": {
            "Stop": [
                {"hooks": [{"type": "command", "command": "notify-send done"}]}
            ],
            "PostToolUse": [
                {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "fmt"}]}
            ],
        },
    }
    path.write_text(json.dumps(original), encoding="utf-8")

    theustad.main(["install-hooks"])
    settings = json.loads(path.read_text(encoding="utf-8"))

    assert settings["model"] == "keep-me"
    assert settings["hooks"]["PostToolUse"] == original["hooks"]["PostToolUse"]
    assert {"type": "command", "command": "notify-send done"} in [
        handler for group in settings["hooks"]["Stop"] for handler in group["hooks"]
    ]
    assert json.loads(Path(f"{path}{claudesettings.BACKUP_SUFFIX}").read_text()) == original


def test_install_replaces_a_handler_from_another_checkout():
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    stale = {
        "type": "command",
        "command": shlex.join(["/old/python", "/old/clone/theustad.py", "hook", "claude", "Stop"]),
        "timeout": 315,
    }
    path.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [stale]}]}}), encoding="utf-8")

    theustad.main(["install-hooks"])
    commands = our_commands(json.loads(path.read_text(encoding="utf-8")))

    assert len(commands["Stop"]) == 1
    assert "/old/clone" not in commands["Stop"][0]


def test_uninstall_removes_only_ours():
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    other = {"type": "command", "command": "notify-send done"}
    path.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [other]}]}}), encoding="utf-8")
    theustad.main(["install-hooks"])

    assert theustad.main(["uninstall-hooks"]) == 0
    settings = json.loads(path.read_text(encoding="utf-8"))

    assert claudesettings.installed_handlers(settings) == {}
    assert settings["hooks"] == {"Stop": [{"hooks": [other]}]}
    assert theustad.main(["uninstall-hooks"]) == 1


def test_invalid_settings_are_never_rewritten(capsys):
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json", encoding="utf-8")

    assert theustad.main(["install-hooks"]) == 2
    assert path.read_text(encoding="utf-8") == "{ not json"
    assert "not valid JSON" in capsys.readouterr().err


def test_dry_run_writes_nothing(capsys):
    assert theustad.main(["install-hooks", "--dry-run"]) == 0

    assert not settings_file().exists()
    printed = json.loads(capsys.readouterr().out)
    assert set(claudesettings.installed_handlers(printed)) == {"SessionStart", "Stop"}


@pytest.mark.skipif(os.name != "posix", reason="symlinked dotfiles are a POSIX setup")
def test_symlinked_settings_are_written_through(tmp_path):
    real = tmp_path / "dotfiles" / "claude-settings.json"
    real.parent.mkdir()
    real.write_text("{}", encoding="utf-8")
    link = settings_file()
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(real)

    theustad.main(["install-hooks"])

    assert link.is_symlink()
    assert set(claudesettings.installed_handlers(json.loads(real.read_text()))) == {
        "SessionStart",
        "Stop",
    }


def test_disabled_hooks_are_reported(capsys):
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"disableAllHooks": true}', encoding="utf-8")

    theustad.main(["install-hooks"])

    assert "disableAllHooks" in capsys.readouterr().err


def test_enroll_points_at_install_hooks_until_they_are_installed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    repo = _repo(tmp_path)

    theustad.main(["enroll", "--repo", str(repo)])
    assert "install-hooks" in capsys.readouterr().out

    theustad.main(["install-hooks"])
    capsys.readouterr()
    theustad.main(["enroll", "--repo", str(repo)])
    assert "HOOKS installed in" in capsys.readouterr().out


def test_enroll_refuses_a_deadline_the_installed_hooks_would_cancel(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    short = {
        "type": "command",
        "command": shlex.join(["/usr/bin/python3", "/x/theustad.py", "hook", "claude", "Stop"]),
        "timeout": 60,
    }
    path.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [short]}]}}), encoding="utf-8")
    repo = _repo(tmp_path)

    assert theustad.main(["enroll", "--repo", str(repo), "--timeout", "120"]) == 2
    assert "install-hooks" in capsys.readouterr().err
    assert enrollment.load_policy(repo) is None


def test_enroll_refuses_a_deadline_above_the_installed_ceiling(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    repo = _repo(tmp_path)

    assert theustad.main(["enroll", "--repo", str(repo), "--timeout", "3590"]) == 2
    assert "ceiling" in capsys.readouterr().err


def test_status_reports_hook_installation(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    repo = _repo(tmp_path)
    theustad.main(["enroll", "--repo", str(repo)])
    capsys.readouterr()

    theustad.main(["status", "--repo", str(repo)])
    assert "CLAUDE_HOOKS not-installed" in capsys.readouterr().out

    theustad.main(["install-hooks"])
    capsys.readouterr()
    theustad.main(["status", "--repo", str(repo)])
    assert "CLAUDE_HOOKS installed" in capsys.readouterr().out


def _plugin_hook(event, payload, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return hookadapter.main([claudesettings.PLUGIN_VENDOR, event])


def _stop_payload(repo, session_id="plugin-session"):
    return {
        "session_id": session_id,
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": str(repo),
        "permission_mode": "default",
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "last_assistant_message": "Done.",
    }


def test_plugin_hook_acts_as_the_claude_hook_when_settings_have_none(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    repo = _repo(tmp_path)
    theustad.main(["enroll", "--repo", str(repo), "--no-census"])
    capsys.readouterr()

    # Enrolled, but no SessionStart ran for this session: the claude vendor
    # blocks, and so must the plugin, because it is the same handler.
    assert _plugin_hook("Stop", _stop_payload(repo), monkeypatch) == hookadapter.BLOCK
    assert "no protected-input baseline" in capsys.readouterr().err


def test_plugin_hook_stands_down_when_settings_run_theustad(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    repo = _repo(tmp_path)
    theustad.main(["enroll", "--repo", str(repo), "--no-census"])
    theustad.main(["install-hooks"])
    capsys.readouterr()

    assert _plugin_hook("Stop", _stop_payload(repo), monkeypatch) == hookadapter.ALLOW
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_plugin_hook_does_not_stand_down_for_unreadable_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ broken", encoding="utf-8")

    assert claudesettings.covers("Stop") is False


def test_a_plugin_cache_copy_never_installs_settings_hooks(tmp_path, monkeypatch, capsys):
    # The cache is versioned and replaced on every plugin update; a settings
    # hook pointing into it would break, and block, after the next update.
    cache_copy = (
        claudesettings.user_settings_path().parent
        / "plugins" / "cache" / "theustad" / "theustad" / "abc123" / "theustad.py"
    )
    cache_copy.parent.mkdir(parents=True)
    cache_copy.write_text("", encoding="utf-8")
    monkeypatch.setattr(theustad, "__file__", str(cache_copy))

    assert theustad.main(["install-hooks"]) == 2
    assert "plugin cache" in capsys.readouterr().err
    assert not settings_file().exists()

    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    theustad.main(["enroll", "--repo", str(_repo(tmp_path))])
    output = capsys.readouterr().out
    assert "HOOKS provided by the TheUstad Claude Code plugin" in output
    assert "install-hooks" not in output.split("Or merge", 1)[0]


def test_no_home_directory_does_not_stop_enrollment(tmp_path, monkeypatch, capsys):
    # Windows raises from Path.home() when neither USERPROFILE nor HOME is
    # set, which is how a minimal environment launches a hook or enroll.
    def no_home():
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(no_home))
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    repo = _repo(tmp_path)

    assert theustad.main(["enroll", "--repo", str(repo)]) == 0
    assert theustad.main(["status", "--repo", str(repo)]) == 0
    assert "CLAUDE_HOOKS unknown" in capsys.readouterr().out
    assert claudesettings.covers("Stop") is False
    assert claudesettings.in_plugin_cache(Path(theustad.__file__)) is False

    assert theustad.main(["install-hooks"]) == 2
    assert "CLAUDE_CONFIG_DIR" in capsys.readouterr().err


def _write_handler(command_argv, **extra):
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = {"type": "command", "command": shlex.join(command_argv), **extra}
    path.write_text(
        json.dumps({"hooks": {event: [{"hooks": [dict(handler, command=shlex.join([*command_argv[:-1], event]))]}] for event in claudesettings.HOOK_EVENTS}}),
        encoding="utf-8",
    )


@pytest.mark.parametrize("missing", ["interpreter", "cli"])
def test_plugin_does_not_defer_to_a_handler_that_cannot_start(
    tmp_path, monkeypatch, capsys, missing
):
    # A missing interpreter exits 127, which Claude Code treats as
    # non-blocking: deferring to it would leave the session unenforced.
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    interpreter = sys.executable if missing == "cli" else str(tmp_path / "gone" / "python3")
    cli = str(tmp_path / "gone" / "theustad.py") if missing == "cli" else theustad.__file__
    _write_handler([interpreter, cli, "hook", "claude", "Stop"], timeout=3600)
    repo = _repo(tmp_path)
    theustad.main(["enroll", "--repo", str(repo), "--no-census"])
    capsys.readouterr()

    assert claudesettings.covers("Stop") is False
    # So the plugin's copy does the work, exactly as the claude vendor would.
    assert _plugin_hook("Stop", _stop_payload(repo), monkeypatch) == hookadapter.BLOCK
    assert "no protected-input baseline" in capsys.readouterr().err

    theustad.main(["status", "--repo", str(repo)])
    assert "CLAUDE_HOOKS stale" in capsys.readouterr().out


@pytest.mark.parametrize("timeout", [None, "600", True, -5])
def test_an_installed_handler_without_a_usable_timeout_counts_as_the_host_default(
    tmp_path, monkeypatch, capsys, timeout
):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    extra = {} if timeout is None else {"timeout": timeout}
    _write_handler([sys.executable, theustad.__file__, "hook", "claude", "Stop"], **extra)
    repo = _repo(tmp_path)

    # 900 s plus the margin outlives the host's 600 s default.
    assert theustad.main(["enroll", "--repo", str(repo), "--timeout", "900"]) == 2
    assert "600s" in capsys.readouterr().err
    assert enrollment.load_policy(repo) is None
    # A deadline the default does hold is accepted.
    assert theustad.main(["enroll", "--repo", str(repo), "--timeout", "300"]) == 0
