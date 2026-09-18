import json
import os
from pathlib import Path

import pytest

from theustadlib import enrollment
from theustadlib.freezer import DEFAULT_PATTERNS, check, freeze
from theustadlib.verifier import default_argv


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_ok.py").write_text("def test_ok(): assert True\n")
    (repo / "pytest.ini").write_text("[pytest]\n")
    return repo


def _policy(repo: Path) -> enrollment.Policy:
    return enrollment.Policy(
        repo=str(repo),
        verifier_argv=tuple(default_argv()),
    )


def test_policy_round_trip_ignores_unknown_keys(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    policy = _policy(repo)
    path = enrollment.save_policy(policy)
    value = json.loads(path.read_text())
    value["future_field"] = {"safe": True}
    path.write_text(json.dumps(value))

    loaded = enrollment.load_policy(repo)

    assert loaded == policy
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_manifest_round_trip_stays_usable_by_freezer(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    state_dir = tmp_path / "external" / "state"
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    manifest = freeze(repo, DEFAULT_PATTERNS, state_dir)

    enrollment.save_manifest(state_dir, manifest)
    loaded = enrollment.load_manifest(state_dir, repo)

    assert loaded == manifest
    assert check(repo, loaded).clean


def test_enrollment_key_is_stable_for_equivalent_paths(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    link = tmp_path / "link"
    try:
        link.symlink_to(repo, target_is_directory=True)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("native Windows process lacks symlink privilege")
        raise

    assert enrollment.enrollment_key(repo) == enrollment.enrollment_key("repo/")
    assert enrollment.enrollment_key(repo) == enrollment.enrollment_key(link)


def test_theustad_home_inside_repo_is_refused(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setenv("THEUSTAD_HOME", str(repo / ".state"))

    with pytest.raises(ValueError, match="outside"):
        enrollment.save_policy(_policy(repo))


def test_session_keys_do_not_collide_after_sanitization(tmp_path, monkeypatch):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    repo = _repo(tmp_path)

    first = enrollment.session_state_dir(repo, "claude", "a/b")
    second = enrollment.session_state_dir(repo, "claude", "ab")

    assert first != second
    assert first.parent == second.parent


def test_block_counter_lifecycle(tmp_path):
    state = tmp_path / "state"

    assert enrollment.block_count(state) == 0
    assert enrollment.bump_blocks(state) == 1
    assert enrollment.bump_blocks(state) == 2
    enrollment.reset_blocks(state)
    assert enrollment.block_count(state) == 0


@pytest.mark.parametrize("max_blocks", [0, 8, 100])
def test_policy_respects_claude_retry_ceiling(tmp_path, max_blocks):
    repo = _repo(tmp_path)

    with pytest.raises(ValueError, match="max_blocks"):
        enrollment.Policy(
            repo=str(repo),
            verifier_argv=("pytest",),
            max_blocks=max_blocks,
        )


def test_hook_defaults_protect_project_hook_configuration():
    assert ".claude/settings.json" in enrollment.HOOK_PATTERNS
    assert ".claude/settings.local.json" in enrollment.HOOK_PATTERNS


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("verifier_argv", "pytest -q"),
        ("patterns", "tests/**"),
        ("require_claim", "false"),
        ("timeout", "nan"),
    ],
)
def test_malformed_external_policy_fails_closed(tmp_path, monkeypatch, field, value):
    repo = _repo(tmp_path)
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    path = enrollment.save_policy(_policy(repo))
    policy = json.loads(path.read_text())
    policy[field] = value
    path.write_text(json.dumps(policy))

    with pytest.raises(ValueError, match="invalid enrollment policy"):
        enrollment.load_policy(repo)
