import io
import json
import shlex
import sys
from pathlib import Path

import theustad
from theustadlib import enrollment


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_ok.py").write_text("def test_ok(): assert True\n")
    return repo


def test_enroll_writes_fixed_policy_and_absolute_hook_commands(
    tmp_path, monkeypatch, capsys
):
    repo = _repo(tmp_path)
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))

    code = theustad.main(["enroll", "--repo", str(repo)])

    assert code == 0
    policy = enrollment.load_policy(repo)
    assert policy is not None
    assert Path(policy.verifier_argv[0]).is_absolute()
    output = capsys.readouterr().out
    settings = json.loads(output[output.index("{") :])
    for event in ("SessionStart", "Stop"):
        command = settings["hooks"][event][0]["hooks"][0]["command"]
        argv = shlex.split(command)
        assert Path(argv[0]).is_absolute()
        assert Path(argv[1]).is_absolute()
        assert argv[-3:] == ["hook", "claude", event]


def test_status_unenrolled_is_nonzero(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path)
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))

    assert theustad.main(["status", "--repo", str(repo)]) == 1
    assert "NOT_ENROLLED" in capsys.readouterr().out


def test_unenroll_requires_explicit_confirmation(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    theustad.main(["enroll", "--repo", str(repo)])

    assert theustad.main(["unenroll", "--repo", str(repo)]) == 2
    assert enrollment.load_policy(repo) is not None
    assert theustad.main(["unenroll", "--repo", str(repo), "--yes"]) == 0
    assert enrollment.load_policy(repo) is None


def test_hook_cli_rejects_policy_injection_without_reading_payload(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))

    code = theustad.main(
        ["hook", "claude", "Stop", "--", "--verifier", "echo ok"]
    )

    assert code == 2
    assert "forbidden" in capsys.readouterr().err


def test_wrapper_parser_remains_backward_compatible():
    args = theustad.build_parser().parse_args(["--repo", "."])

    assert args.repo == Path(".")
