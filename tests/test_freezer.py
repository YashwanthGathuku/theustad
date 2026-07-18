from pathlib import Path

import pytest

from gatelib import freezer


EXPECTED_DEFAULT_PATTERNS = (
    "tests/**",
    "pytest.ini",
    "conftest.py",
    "**/conftest.py",
    "pyproject.toml",
    "setup.cfg",
    "tox.ini",
    "pytest.py",
    "pytest/**",
    "sitecustomize.py",
    "usercustomize.py",
)


def _seed_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    state_dir = tmp_path / "gate-state"
    (repo / "tests").mkdir(parents=True)
    (repo / "app").mkdir()
    (repo / "tests" / "test_guard.py").write_text("def test_guard(): pass\n")
    (repo / "app" / "code.py").write_text("VALUE = 1\n")
    (repo / "pytest.ini").write_text("[pytest]\n")
    return repo, state_dir


def test_default_patterns_match_the_security_contract():
    assert freezer.DEFAULT_PATTERNS == EXPECTED_DEFAULT_PATTERNS


def test_freeze_snapshots_protected_files_outside_repo(tmp_path):
    repo, state_dir = _seed_repo(tmp_path)

    manifest = freezer.freeze(repo, freezer.DEFAULT_PATTERNS, state_dir)

    assert manifest.repo == repo.resolve()
    assert manifest.state_dir == state_dir.resolve()
    assert manifest.snapshot_dir.parent == state_dir.resolve()
    assert not manifest.snapshot_dir.is_relative_to(repo.resolve())
    assert manifest.snapshot_dir.name.startswith("snapshot-")
    print(f"repository={repo.resolve()}")
    print(f"snapshot={manifest.snapshot_dir}")

    entry = manifest.entries["tests/test_guard.py"]
    assert entry.file_type == "file"
    assert len(entry.sha256) == 64
    assert entry.snapshot_path.read_text() == "def test_guard(): pass\n"
    assert "pytest.ini" in manifest.entries
    assert "app/code.py" not in manifest.entries


def test_freeze_refuses_state_dir_inside_repo(tmp_path):
    repo, _ = _seed_repo(tmp_path)

    with pytest.raises(ValueError, match="outside the repository"):
        freezer.freeze(repo, freezer.DEFAULT_PATTERNS, repo / ".gate-state")


def test_check_is_clean_immediately_after_freeze(tmp_path):
    repo, state_dir = _seed_repo(tmp_path)
    manifest = freezer.freeze(repo, freezer.DEFAULT_PATTERNS, state_dir)

    tampering = freezer.check(repo, manifest)

    assert tampering.clean
    assert not tampering
    assert tampering.modified == []
    assert tampering.deleted == []
    assert tampering.added == []


def test_check_reports_modified_protected_test(tmp_path):
    repo, state_dir = _seed_repo(tmp_path)
    manifest = freezer.freeze(repo, freezer.DEFAULT_PATTERNS, state_dir)
    (repo / "tests" / "test_guard.py").write_text("def test_guard(): assert False\n")

    tampering = freezer.check(repo, manifest)

    assert tampering.modified == ["tests/test_guard.py"]
    assert tampering.deleted == []
    assert tampering.added == []


def test_check_reports_deleted_protected_test(tmp_path):
    repo, state_dir = _seed_repo(tmp_path)
    manifest = freezer.freeze(repo, freezer.DEFAULT_PATTERNS, state_dir)
    (repo / "tests" / "test_guard.py").unlink()

    tampering = freezer.check(repo, manifest)

    assert tampering.modified == []
    assert tampering.deleted == ["tests/test_guard.py"]
    assert tampering.added == []


def test_check_reports_added_configuration_and_shadowing_paths(tmp_path):
    repo, state_dir = _seed_repo(tmp_path)
    manifest = freezer.freeze(repo, freezer.DEFAULT_PATTERNS, state_dir)
    (repo / "conftest.py").write_text("# planted\n")
    (repo / "pytest.py").write_text("# planted\n")
    (repo / "pytest").mkdir()
    (repo / "pytest" / "__main__.py").write_text("# planted\n")
    (repo / "sitecustomize.py").write_text("# planted\n")

    tampering = freezer.check(repo, manifest)

    assert {
        "conftest.py",
        "pytest.py",
        "pytest/__main__.py",
        "sitecustomize.py",
    } <= set(tampering.added)
    assert tampering.modified == []
    assert tampering.deleted == []


def test_check_ignores_unprotected_application_edits(tmp_path):
    repo, state_dir = _seed_repo(tmp_path)
    manifest = freezer.freeze(repo, freezer.DEFAULT_PATTERNS, state_dir)
    (repo / "app" / "code.py").write_text("VALUE = 2\n")

    assert freezer.check(repo, manifest).clean


def test_check_reports_file_to_directory_type_change(tmp_path):
    repo, state_dir = _seed_repo(tmp_path)
    manifest = freezer.freeze(repo, freezer.DEFAULT_PATTERNS, state_dir)
    protected = repo / "tests" / "test_guard.py"
    protected.unlink()
    protected.mkdir()

    tampering = freezer.check(repo, manifest)

    assert tampering.modified == ["tests/test_guard.py"]
    assert tampering.deleted == []


def test_check_reports_symlink_without_following_its_target(tmp_path):
    repo, state_dir = _seed_repo(tmp_path)
    manifest = freezer.freeze(repo, freezer.DEFAULT_PATTERNS, state_dir)
    protected = repo / "tests" / "test_guard.py"
    external = tmp_path / "external.py"
    external.write_text("def test_guard(): pass\n")
    protected.unlink()
    try:
        protected.symlink_to(external)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("native Windows process lacks symlink privilege")
        raise

    tampering = freezer.check(repo, manifest)

    assert tampering.modified == ["tests/test_guard.py"]
    assert external.read_text() == "def test_guard(): pass\n"


def test_restore_returns_manifest_to_clean_and_removes_planted_paths(tmp_path):
    repo, state_dir = _seed_repo(tmp_path)
    manifest = freezer.freeze(repo, freezer.DEFAULT_PATTERNS, state_dir)
    (repo / "tests" / "test_guard.py").unlink()
    (repo / "pytest.ini").write_text("[pytest]\naddopts = --ignore=tests\n")
    (repo / "conftest.py").write_text("# planted\n")
    (repo / "pytest.py").write_text("# planted\n")
    (repo / "pytest").mkdir()
    (repo / "pytest" / "__main__.py").write_text("# planted\n")
    (repo / "sitecustomize.py").write_text("# planted\n")
    (repo / "app" / "code.py").write_text("VALUE = 2\n")

    freezer.restore(repo, manifest)

    assert freezer.check(repo, manifest).clean
    assert (repo / "tests" / "test_guard.py").read_text() == (
        "def test_guard(): pass\n"
    )
    assert (repo / "pytest.ini").read_text() == "[pytest]\n"
    assert not (repo / "conftest.py").exists()
    assert not (repo / "pytest.py").exists()
    assert not (repo / "pytest").exists()
    assert not (repo / "sitecustomize.py").exists()
    assert (repo / "app" / "code.py").read_text() == "VALUE = 2\n"


def test_restore_replaces_protected_directory_with_original_file(tmp_path):
    repo, state_dir = _seed_repo(tmp_path)
    manifest = freezer.freeze(repo, freezer.DEFAULT_PATTERNS, state_dir)
    protected = repo / "tests" / "test_guard.py"
    protected.unlink()
    protected.mkdir()
    (protected / "planted.py").write_text("# planted\n")

    freezer.restore(repo, manifest)

    assert protected.is_file()
    assert protected.read_text() == "def test_guard(): pass\n"
    assert freezer.check(repo, manifest).clean
