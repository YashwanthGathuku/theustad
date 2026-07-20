from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.gate_plugin import (
    PluginError,
    allocate_state_dir,
    default_state_home,
    doctor,
    ensure_supported_platform,
    resolve_repo,
)


def test_native_windows_fails_closed():
    with pytest.raises(PluginError, match="WSL 2"):
        ensure_supported_platform(os_name="nt")


def test_posix_platform_is_supported():
    ensure_supported_platform(os_name="posix")


def test_resolve_repo_uses_git_root_from_nested_directory(tmp_path):
    repo = tmp_path / "repo with spaces"
    repo.mkdir()
    subprocess.run(
        ["git", "init", str(repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    nested = repo / "src"
    nested.mkdir()

    assert resolve_repo(None, cwd=nested) == repo.resolve()


def test_resolve_repo_rejects_non_git_directory(tmp_path):
    with pytest.raises(PluginError, match="Git repository"):
        resolve_repo(tmp_path)


def test_gate_state_home_overrides_xdg_and_default(tmp_path):
    gate_home = tmp_path / "gate-home"
    xdg_home = tmp_path / "xdg"

    assert default_state_home(
        environ={
            "GATE_STATE_HOME": str(gate_home),
            "XDG_STATE_HOME": str(xdg_home),
        },
        home=tmp_path / "home",
    ) == gate_home.resolve()


def test_xdg_state_home_is_used_when_gate_override_is_absent(tmp_path):
    xdg_home = tmp_path / "xdg"

    assert default_state_home(
        environ={"XDG_STATE_HOME": str(xdg_home)},
        home=tmp_path / "home",
    ) == (xdg_home / "gate").resolve()


def test_default_state_home_uses_user_local_state(tmp_path):
    assert default_state_home(environ={}, home=tmp_path / "home") == (
        tmp_path / "home" / ".local" / "state" / "gate"
    ).resolve()


def test_allocate_state_dir_is_external_and_unique(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    state_home = tmp_path / "state"

    first = allocate_state_dir(repo, state_home=state_home)
    second = allocate_state_dir(repo, state_home=state_home)

    assert first != second
    assert not first.is_relative_to(repo)
    assert first.is_dir()
    assert second.is_dir()
    assert first.parent == second.parent


def test_allocate_state_dir_rejects_state_home_inside_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(PluginError, match="outside the target repository"):
        allocate_state_dir(repo, state_home=repo / ".gate")


class RecordingRunner:
    def __init__(self):
        self.calls: list[tuple[tuple[str, ...], Path | None]] = []

    def __call__(
        self,
        argv: list[str],
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = tuple(argv)
        self.calls.append((command, cwd))
        if command[-1:] == ("--version",):
            return subprocess.CompletedProcess(argv, 0, "codex-cli 0.145.0\n", "")
        if command[-2:] == ("exec", "--help"):
            return subprocess.CompletedProcess(
                argv,
                0,
                "Usage: codex exec [OPTIONS]\n--json\n--sandbox <MODE>\n",
                "",
            )
        if command[-3:] == ("exec", "resume", "--help"):
            return subprocess.CompletedProcess(
                argv,
                0,
                "Usage: codex exec resume [SESSION_ID] [PROMPT]\n",
                "",
            )
        if command[-2:] == ("login", "status"):
            return subprocess.CompletedProcess(argv, 0, "Logged in\n", "")
        if "import pytest" in command[-1]:
            return subprocess.CompletedProcess(argv, 0, "9.0.1\n", "")
        raise AssertionError(f"unexpected command: {command}")


def test_doctor_checks_codex_contract_login_and_isolated_pytest(tmp_path):
    runner = RecordingRunner()
    codex = tmp_path / "bin" / "codex"
    state_home = tmp_path.parent / f"{tmp_path.name}-state"

    report = doctor(
        tmp_path,
        os_name="posix",
        command_runner=runner,
        which=lambda name: str(codex) if name == "codex" else None,
        state_home=state_home,
    )

    commands = [call[0] for call in runner.calls]
    assert (str(codex), "--version") in commands
    assert (str(codex), "exec", "--help") in commands
    assert (str(codex), "exec", "resume", "--help") in commands
    assert (str(codex), "login", "status") in commands
    assert any(command[1:3] == ("-I", "-c") for command in commands)
    assert report.codex == codex
    assert report.codex_version == "codex-cli 0.145.0"
    assert report.verifier == "isolated pytest"
    assert report.state_home == state_home.resolve()


def test_doctor_custom_verifier_skips_pytest_import(tmp_path):
    runner = RecordingRunner()
    state_home = tmp_path.parent / f"{tmp_path.name}-state"

    report = doctor(
        tmp_path,
        verifier="python -m unittest",
        os_name="posix",
        command_runner=runner,
        which=lambda name: "/usr/bin/codex" if name == "codex" else None,
        state_home=state_home,
    )

    assert not any("import pytest" in call[0][-1] for call in runner.calls)
    assert report.verifier == "python -m unittest"


def test_doctor_rejects_missing_codex_json_flag(tmp_path):
    runner = RecordingRunner()

    def missing_json(argv, cwd=None):
        result = runner(argv, cwd)
        if tuple(argv[-2:]) == ("exec", "--help"):
            return subprocess.CompletedProcess(argv, 0, "--sandbox <MODE>\n", "")
        return result

    with pytest.raises(PluginError, match="--json"):
        doctor(
            tmp_path,
            os_name="posix",
            command_runner=missing_json,
            which=lambda name: "/usr/bin/codex" if name == "codex" else None,
            state_home=tmp_path / "state",
        )
