from __future__ import annotations

import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from scripts.gate_plugin import (
    PLUGIN_ROOT,
    PluginError,
    allocate_state_dir,
    build_audit_argv,
    build_gate_argv,
    build_parser,
    default_state_home,
    doctor,
    ensure_supported_platform,
    main,
    resolve_repo,
    run_audit,
    run_gate,
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


def test_run_parser_requires_exactly_one_task_source():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["run"])
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["run", "--task-text", "fix it", "--task-file", "task.md"]
        )


def test_gate_argv_uses_absolute_python_plugin_core_and_state_dir(tmp_path):
    state = tmp_path / "state"
    argv = build_gate_argv(
        repo=tmp_path / "repo with spaces",
        task_path=state / "task.txt",
        state_dir=state,
        verifier=None,
        timeout=60,
        max_retries=2,
    )

    assert Path(argv[0]).is_absolute()
    assert Path(argv[0]) == Path(sys.executable).resolve()
    assert Path(argv[1]) == PLUGIN_ROOT / "gate.py"
    assert argv[argv.index("--state-dir") + 1] == str(state)
    assert argv[argv.index("--log") + 1] == str(state / "logs")
    assert "repo with spaces" in argv[argv.index("--repo") + 1]


def test_custom_verifier_is_forwarded_as_one_argument(tmp_path):
    argv = build_gate_argv(
        repo=tmp_path / "repo",
        task_path=tmp_path / "task.txt",
        state_dir=tmp_path / "state",
        verifier="python -m pytest checks -q",
        timeout=60,
        max_retries=2,
    )

    assert argv[argv.index("--verifier") + 1] == "python -m pytest checks -q"


def test_task_text_is_copied_to_external_state_and_exit_code_passes_through(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    state = tmp_path / "external-state"
    state.mkdir()
    calls = []

    monkeypatch.setattr("scripts.gate_plugin.resolve_repo", lambda repo, cwd=None: repo)
    monkeypatch.setattr("scripts.gate_plugin.doctor", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "scripts.gate_plugin.allocate_state_dir",
        lambda repo, state_home=None: state,
    )

    def process_runner(argv, cwd):
        calls.append((argv, cwd))
        return 7

    args = build_parser().parse_args(
        ["run", "--repo", str(repo), "--task-text", "Fix the parser"]
    )
    result = run_gate(args, process_runner=process_runner)

    assert result == 7
    assert (state / "task.txt").read_text(encoding="utf-8") == "Fix the parser"
    argv, cwd = calls[0]
    assert cwd == PLUGIN_ROOT
    assert argv[argv.index("--task") + 1] == str(state / "task.txt")


def test_task_file_is_resolved_without_copying(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    task = repo / "task.md"
    task.write_text("Use this task", encoding="utf-8")
    state = tmp_path / "external-state"
    state.mkdir()
    calls = []

    monkeypatch.setattr("scripts.gate_plugin.resolve_repo", lambda repo, cwd=None: repo)
    monkeypatch.setattr("scripts.gate_plugin.doctor", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "scripts.gate_plugin.allocate_state_dir",
        lambda repo, state_home=None: state,
    )

    def process_runner(argv, cwd):
        calls.append((argv, cwd))
        return 0

    args = build_parser().parse_args(
        ["run", "--repo", str(repo), "--task-file", str(task)]
    )
    result = run_gate(args, process_runner=process_runner)

    assert result == 0
    argv, _ = calls[0]
    assert argv[argv.index("--task") + 1] == str(task.resolve())
    assert not (state / "task.txt").exists()


def test_missing_task_file_is_rejected_before_launch(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    state = tmp_path / "external-state"
    state.mkdir()
    monkeypatch.setattr("scripts.gate_plugin.resolve_repo", lambda repo, cwd=None: repo)
    monkeypatch.setattr("scripts.gate_plugin.doctor", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "scripts.gate_plugin.allocate_state_dir",
        lambda repo, state_home=None: state,
    )

    args = build_parser().parse_args(
        ["run", "--repo", str(repo), "--task-file", str(repo / "missing.md")]
    )
    with pytest.raises(PluginError, match="task file"):
        run_gate(args, process_runner=lambda argv, cwd: 0)


def test_audit_uses_bundled_verify_chain_and_passes_exit_code(tmp_path):
    log = tmp_path / "audit.jsonl"
    log.write_text("{}\n", encoding="utf-8")
    calls = []

    def process_runner(argv, cwd):
        calls.append((argv, cwd))
        return 9

    result = run_audit(
        Namespace(log_path=log),
        process_runner=process_runner,
    )

    assert result == 9
    argv, cwd = calls[0]
    assert argv == build_audit_argv(log.resolve())
    assert Path(argv[0]) == Path(sys.executable).resolve()
    assert Path(argv[1]) == PLUGIN_ROOT / "verify_chain.py"
    assert cwd == PLUGIN_ROOT


def test_main_prints_plugin_error_and_exits_two(monkeypatch, capsys):
    def fail(args, process_runner=None):
        raise PluginError("preflight failed")

    monkeypatch.setattr("scripts.gate_plugin.run_gate", fail)

    assert main(["run", "--task-text", "fix it"]) == 2
    assert "GATE_PLUGIN_ERROR preflight failed" in capsys.readouterr().err
