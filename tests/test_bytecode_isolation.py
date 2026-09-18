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
    # --cmd is parsed with POSIX shlex, which eats Windows backslashes, so
    # paths embedded in a command string use forward slashes.
    python = Path(sys.executable).as_posix()
    script = agent.as_posix()
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "theustad.py"),
            "--repo",
            str(repo),
            "--task",
            "Make add() return the sum.",
            "--cmd",
            f"{python} {script}",
            "--resume-cmd",
            f"{python} {script} {{thread_id}}",
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
        f"{Path(sys.executable).as_posix()} -m pytest -q",
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


@pytest.mark.parametrize(
    "command",
    [
        "{python} -I -m pytest -q",
        "{python} -E -m pytest -q",
        "{python} -I script.py",
        "{python} -IE -m pytest",
        "py -I -m pytest",
        # CPython reads an empty prefix as no prefix: sys.pycache_prefix is
        # None and bytecode still lands beside the source.
        "{python} -I -X pycache_prefix= -m pytest",
        "{python} -IX pycache_prefix= -m pytest",
        # -X pycache_prefix with no value at all sets no prefix either.
        "{python} -I -X pycache_prefix -m pytest",
    ],
)
def test_a_verifier_that_ignores_the_bytecode_variable_is_refused(command):
    # -I implies -E, so isolated Python never sees PYTHONDONTWRITEBYTECODE and
    # would write into the protected tree, failing an honest run as TAMPERED.
    from theustadlib.verifier import parse_command

    with pytest.raises(ValueError, match="isolated Python"):
        parse_command(command.format(python=Path(sys.executable).as_posix()))


@pytest.mark.parametrize(
    "command",
    [
        "{python} -I -B -m pytest -q",
        "{python} -IB -m pytest -q",
        "{python} -B -I -m pytest -q",
        "{python} -m pytest -q",
        "{python} -I -X pycache_prefix=/tmp/theustad-cache -m pytest",
        "{python} -IX pycache_prefix=/tmp/theustad-cache -m pytest",
        "npm test",
        "pytest -q",
    ],
)
def test_a_verifier_that_cannot_write_protected_bytecode_is_accepted(command):
    from theustadlib.verifier import parse_command

    argv = parse_command(command.format(python=Path(sys.executable).as_posix()))

    assert argv


def test_the_default_verifier_is_accepted_by_its_own_rule():
    from theustadlib.verifier import default_argv, ignores_bytecode_environment

    assert not ignores_bytecode_environment(default_argv())


def test_an_isolated_verifier_with_B_reaches_verified(tmp_path):
    repo = tmp_path / "repo"
    _seed_repo(repo)
    python = Path(sys.executable).as_posix()

    result = _run_theustad(
        repo,
        tmp_path / "state",
        _agent_script(tmp_path),
        "--verifier",
        f"{python} -I -B -m pytest -q",
    )

    assert "TAMPERED" not in result.stdout, result.stdout
    assert "FINAL VERIFIED" in result.stdout, result.stdout
    assert not (repo / "tests" / "__pycache__").exists()


# Every interpreter-flag spelling worth distinguishing. The parser's verdict is
# checked against what CPython actually does, not against what it was written
# to expect: two earlier defects here were flag spellings that looked handled
# and were not.
_FLAG_SPELLINGS = [
    [],
    ["-B"],
    ["-I"],
    ["-E"],
    ["-I", "-B"],
    ["-IB"],
    ["-BI"],
    ["-I", "-s"],
    ["-u", "-I"],
    ["-I", "-X", "dev"],
    ["-I", "-X", "utf8"],
    ["-I", "-Xutf8"],
    ["-I", "-W", "ignore"],
    ["-I", "-Wignore"],
    ["-I", "-X", "pycache_prefix"],
    ["-I", "-X", "pycache_prefix="],
    ["-IX", "pycache_prefix="],
    ["-I", "-X", "pycache_prefix=PLACEHOLDER"],
    ["-IX", "pycache_prefix=PLACEHOLDER"],
    ["-I", "-X", "utf8", "-B"],
]


def _writes_bytecode_beside_source(flags: list[str], tmp_path: Path) -> bool:
    """Run CPython with these flags and report whether it left a __pycache__."""
    protected = tmp_path / "protected"
    protected.mkdir()
    (protected / "probe_mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    code = f"import sys; sys.path.insert(0, {str(protected)!r}); import probe_mod"
    result = subprocess.run(
        [sys.executable, *flags, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, (flags, result.stderr)
    return (protected / "__pycache__").exists()


@pytest.mark.parametrize("flags", _FLAG_SPELLINGS, ids=lambda f: " ".join(f) or "bare")
def test_the_parser_agrees_with_cpython_on_every_flag_spelling(flags, tmp_path):
    from theustadlib.verifier import ignores_bytecode_environment

    cache = tmp_path / "redirected"
    resolved = [flag.replace("PLACEHOLDER", str(cache)) for flag in flags]

    wrote = _writes_bytecode_beside_source(resolved, tmp_path)
    refused = ignores_bytecode_environment([sys.executable, *resolved, "-m", "pytest"])

    # A verifier that writes beside the source must be refused; one that does
    # not must be accepted. Either mismatch is a defect.
    assert refused == wrote, (
        f"{' '.join(resolved) or '(no flags)'}: parser says "
        f"{'refuse' if refused else 'accept'} but CPython "
        f"{'wrote' if wrote else 'did not write'} bytecode beside the source"
    )
