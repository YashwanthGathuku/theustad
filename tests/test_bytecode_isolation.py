"""Honest agents and custom verifiers must not look like tampering.

Any real coding agent runs the project's test suite while it works, and many
projects configure a custom verifier that is plain ``pytest``.  Both write
``tests/__pycache__`` bytecode inside the protected tree, which the next
manifest check would otherwise report as added protected paths.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _seed_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n", encoding="utf-8")
    app = repo / "app"
    app.mkdir()
    (app / "__init__.py").write_text("", encoding="utf-8")
    (app / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    tests = repo / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("", encoding="utf-8")
    (tests / "test_calc.py").write_text(
        "from app.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )


def _agent_script(tmp_path: Path) -> Path:
    script = tmp_path / "agent.py"
    script.write_text(
        "import json, pathlib, subprocess, sys\n"
        'print(json.dumps({"type": "thread.started", "thread_id": "t-1"}), flush=True)\n'
        'pathlib.Path("app/calc.py").write_text("def add(a, b):\\n    return a + b\\n")\n'
        # An honest agent checks its own work before reporting.
        'subprocess.run([sys.executable, "-m", "pytest", "-q"], check=False)\n'
        "print(json.dumps({\n"
        '    "type": "item.completed",\n'
        '    "item": {\n'
        '        "type": "agent_message",\n'
        '        "text": "Fixed add(). All tests pass and the task is complete.",\n'
        "    },\n"
        "}), flush=True)\n",
        encoding="utf-8",
    )
    return script


def _run_theustad(repo: Path, state: Path, agent: Path, *extra: str):
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "theustad.py"),
            "--repo",
            str(repo),
            "--task",
            "Make add() return the sum.",
            "--cmd",
            f"{sys.executable} {agent}",
            "--resume-cmd",
            f"{sys.executable} {agent} {{thread_id}}",
            "--max-retries",
            "1",
            "--state-dir",
            str(state),
            "--no-color",
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )


def test_agent_running_pytest_is_not_reported_as_tampering(tmp_path):
    repo = tmp_path / "repo"
    _seed_repo(repo)

    result = _run_theustad(repo, tmp_path / "state", _agent_script(tmp_path))

    assert "TAMPERED" not in result.stdout, result.stdout
    assert "FINAL VERIFIED" in result.stdout, result.stdout
    assert result.returncode == 0
    assert not (repo / "tests" / "__pycache__").exists()


def test_custom_pytest_verifier_is_not_reported_as_tampering(tmp_path):
    repo = tmp_path / "repo"
    _seed_repo(repo)

    result = _run_theustad(
        repo,
        tmp_path / "state",
        _agent_script(tmp_path),
        "--verifier",
        f"{sys.executable} -m pytest -q",
    )

    assert "TAMPERED" not in result.stdout, result.stdout
    assert "FINAL VERIFIED" in result.stdout, result.stdout
    assert not (repo / "tests" / "__pycache__").exists()


def test_planted_bytecode_is_still_reported_as_tampering(tmp_path):
    repo = tmp_path / "repo"
    _seed_repo(repo)
    planter = tmp_path / "planter.py"
    planter.write_text(
        "import json, pathlib\n"
        'print(json.dumps({"type": "thread.started", "thread_id": "t-2"}), flush=True)\n'
        'cache = pathlib.Path("tests/__pycache__")\n'
        "cache.mkdir(exist_ok=True)\n"
        '(cache / "test_calc.cpython-311.pyc").write_bytes(b"\\x00planted")\n'
        "print(json.dumps({\n"
        '    "type": "item.completed",\n'
        '    "item": {"type": "agent_message", "text": "All tests pass. Done."},\n'
        "}), flush=True)\n",
        encoding="utf-8",
    )

    result = _run_theustad(repo, tmp_path / "state", planter)

    assert "TAMPERED" in result.stdout, result.stdout
    assert not (repo / "tests" / "__pycache__").exists()


def test_child_environment_forces_bytecode_off_without_mutating_os_environ():
    from theustadlib.childenv import child_environment

    environment = child_environment({"PYTHONDONTWRITEBYTECODE": "", "KEEP": "yes"})

    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert environment["KEEP"] == "yes"
    assert "PYTHONDONTWRITEBYTECODE" not in os.environ or os.environ[
        "PYTHONDONTWRITEBYTECODE"
    ] != ""


def test_verifier_subprocess_receives_the_hardened_environment(tmp_path, monkeypatch):
    from theustadlib import verifier

    captured = {}
    real_popen = subprocess.Popen

    def fake_popen(argv, **kwargs):
        captured.update(kwargs)
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    verifier.run([sys.executable, "-c", "pass"], tmp_path, timeout=30)

    assert captured["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert captured["shell"] is False


def test_agent_subprocess_receives_the_hardened_environment(tmp_path, monkeypatch):
    from theustadlib.session import AgentSession

    captured = {}
    real_popen = subprocess.Popen

    def fake_popen(argv, **kwargs):
        captured.update(kwargs)
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    session = AgentSession([sys.executable, "-c", "pass"], [sys.executable, "-c", "pass"], tmp_path, 30)
    session.start("task")

    assert captured["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
