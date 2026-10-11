"""Installing TheUstad's Codex hooks, and telling whether Codex will run them."""

import io
import json
import shlex
import sys
from pathlib import Path

import pytest

import theustad
from theustadlib import claudesettings, codexsettings, enrollment, hookadapter


try:
    import tomllib  # noqa: F401
    HAS_TOMLLIB = True
except ImportError:
    HAS_TOMLLIB = False
needs_tomllib = pytest.mark.skipif(not HAS_TOMLLIB, reason="Python 3.10 has no TOML reader")


@pytest.fixture(autouse=True)
def codex_home(tmp_path, monkeypatch):
    home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    return home


def _hooks(codex_home):
    return json.loads((codex_home / "hooks.json").read_text())


def _repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_ok.py").write_text("def test_ok(): assert True\n")
    return repo


def _trust(codex_home, *, digest=None):
    """What approving the hooks in Codex's /hooks records."""
    path = codex_home / "hooks.json"
    settings = json.loads(path.read_text())
    lines = []
    for event, key, item, matcher in codexsettings._our_entries(path, settings):
        value = digest or codexsettings.handler_hash(event, item, matcher)
        lines.append(f'[hooks.state.{json.dumps(key)}]\ntrusted_hash = "{value}"\n')
    (codex_home / "config.toml").write_text("\n".join(lines))


def test_install_writes_guarded_user_hooks_and_leaves_claude_alone(codex_home, capsys):
    assert theustad.main(["install-hooks", "--agent", "codex"]) == 0
    out = capsys.readouterr().out

    found = claudesettings.installed_handlers(_hooks(codex_home), "codex")
    assert set(found) == {"SessionStart", "Stop"}
    for event, (handler,) in found.items():
        argv = shlex.split(handler["command"])
        assert argv[:4] == ["test", "-e", argv[5], "&&"]
        assert argv[-3:] == ["hook", "codex", event]
        assert handler["timeout"] == claudesettings.HANDLER_TIMEOUT
        assert claudesettings.runnable(handler, vendor="codex")
    assert not claudesettings.user_settings_path().exists()
    # Python 3.10 cannot read config.toml, so it can only say trust is unknown.
    trust = "untrusted" if HAS_TOMLLIB else "unknown"
    assert f"CODEX_TRUST {trust}" in out and "/hooks" in out


def test_install_keeps_other_hooks_and_is_idempotent(codex_home):
    codex_home.mkdir()
    other = {"type": "command", "command": "echo hi"}
    (codex_home / "hooks.json").write_text(
        json.dumps({"hooks": {"Stop": [{"hooks": [other]}]}, "extra": 1})
    )

    theustad.main(["install-hooks", "--agent", "codex"])
    theustad.main(["install-hooks", "--agent", "codex"])

    settings = _hooks(codex_home)
    assert settings["extra"] == 1
    assert settings["hooks"]["Stop"][0]["hooks"] == [other]
    assert [len(v) for v in claudesettings.installed_handlers(settings, "codex").values()] == [1, 1]


def test_uninstall_removes_only_the_named_agents_hooks(codex_home, capsys):
    theustad.main(["install-hooks", "--agent", "codex"])
    theustad.main(["install-hooks"])
    capsys.readouterr()

    assert theustad.main(["uninstall-hooks", "--agent", "codex"]) == 0
    assert claudesettings.installed_handlers(_hooks(codex_home), "codex") == {}
    claude = claudesettings.read_settings(claudesettings.user_settings_path())
    assert set(claudesettings.installed_handlers(claude)) == {"SessionStart", "Stop"}
    assert theustad.main(["uninstall-hooks", "--agent", "codex"]) == 1


def test_the_guard_must_check_the_cli_it_runs():
    good = claudesettings.handler(sys.executable, theustad.__file__, "Stop", "codex")
    forged = dict(good, command=good["command"].replace(
        shlex.quote(theustad.__file__), "/etc/hostname", 1
    ))

    assert claudesettings.runnable(good, vendor="codex")
    assert not claudesettings.runnable(forged, vendor="codex")


def test_trust_hash_matches_what_codex_recorded():
    # Codex 0.162.1 ran this exact handler, without its bypass flag, only
    # with this hash stored as trusted.
    handler = {
        "type": "command",
        "command": "/usr/bin/python3 /opt/theustad/theustad.py hook codex Stop",
        "timeout": 3600,
    }

    assert codexsettings.handler_hash("Stop", handler, None) == (
        "sha256:7c2a794a047c0d0fdf3e112afb50e3b5eef2c1f0911e728f3c3cb8f15e3a1a8b"
    )


@needs_tomllib
def test_status_reports_whether_codex_will_run_the_hooks(tmp_path, codex_home, capsys):
    repo = _repo(tmp_path)
    theustad.main(["enroll", "--repo", str(repo), "--no-census"])

    def status():
        capsys.readouterr()
        theustad.main(["status", "--repo", str(repo)])
        return capsys.readouterr().out

    assert "CODEX_HOOKS not-installed" in status()
    theustad.main(["install-hooks", "--agent", "codex"])
    assert "CODEX_HOOKS untrusted" in status()
    _trust(codex_home)
    assert "CODEX_HOOKS installed" in status()
    _trust(codex_home, digest="sha256:" + "0" * 64)
    assert "changed since you trusted them" in status()
    _trust(codex_home)
    with (codex_home / "config.toml").open("a") as config:
        config.write("\n[features]\nhooks = false\n")
    assert "CODEX_HOOKS disabled" in status()


@pytest.mark.skipif(HAS_TOMLLIB, reason="only Python 3.10 lacks a TOML reader")
def test_status_says_when_it_cannot_read_trust(tmp_path, capsys):
    repo = _repo(tmp_path)
    theustad.main(["enroll", "--repo", str(repo), "--no-census"])
    theustad.main(["install-hooks", "--agent", "codex"])
    capsys.readouterr()

    theustad.main(["status", "--repo", str(repo)])

    assert "trust unknown" in capsys.readouterr().out


def test_enroll_refuses_a_deadline_the_codex_hooks_would_cancel(tmp_path, codex_home, capsys):
    repo = _repo(tmp_path)
    codex_home.mkdir()
    handler = claudesettings.handler(sys.executable, theustad.__file__, "Stop", "codex")
    del handler["timeout"]  # Codex then applies its 600 s default
    (codex_home / "hooks.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": [handler]}]}}))

    assert theustad.main(["enroll", "--repo", str(repo), "--timeout", "900"]) == 2
    assert "600s" in capsys.readouterr().err
    assert enrollment.load_policy(repo) is None


def _faulted_stop(monkeypatch, vendor, *, active):
    def broken(*_args, **_kwargs):
        raise RuntimeError("state is corrupt")

    monkeypatch.setattr(hookadapter, "dispatch", broken)
    payload = {"hook_event_name": "Stop", "session_id": "loop-1", "stop_hook_active": active}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return hookadapter.main([vendor, "Stop"])


def test_a_recurring_fault_cannot_loop_codex_for_ever(monkeypatch, capsys):
    # Codex sets no limit on Stop continuations; Claude Code stops at eight.
    results = [_faulted_stop(monkeypatch, "codex", active=False)]
    results += [_faulted_stop(monkeypatch, "codex", active=True) for _ in range(8)]

    assert results[:8] == [hookadapter.BLOCK] * 8
    assert results[8] == hookadapter.ALLOW
    assert "UNVERIFIED" in capsys.readouterr().err
    # A new turn gets the full bound again.
    assert _faulted_stop(monkeypatch, "codex", active=False) == hookadapter.BLOCK


def test_a_response_that_cannot_be_emitted_counts_toward_the_bound(monkeypatch, capsys):
    # Dispatch succeeds but its output never reaches Codex, on every Stop.
    def unprintable(*_args, **_kwargs):
        return hookadapter.HookResponse(hookadapter.ALLOW, stdout={"bad": object()})

    def stop(active):
        monkeypatch.setattr(hookadapter, "dispatch", unprintable)
        payload = {"hook_event_name": "Stop", "session_id": "loop-2", "stop_hook_active": active}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        return hookadapter.main(["codex", "Stop"])

    results = [stop(False)] + [stop(True) for _ in range(8)]

    assert results[:8] == [hookadapter.BLOCK] * 8
    assert results[8] == hookadapter.ALLOW
    assert "UNVERIFIED" in capsys.readouterr().err


def test_claude_faults_keep_blocking_because_claude_code_bounds_them(monkeypatch):
    results = [_faulted_stop(monkeypatch, "claude", active=True) for _ in range(12)]

    assert set(results) == {hookadapter.BLOCK}
