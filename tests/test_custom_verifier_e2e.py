import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
FAKE_CODEX = ROOT / "fake_codex.py"
SEED = ROOT / "tests" / "fixtures" / "js_repo_seed"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    for child in sorted(path.rglob("*")):
        if child.is_file():
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            digest.update(child.read_bytes())
    return digest.hexdigest()


def test_explicit_absolute_npm_verifier_verifies_without_mutating_protected_inputs(
    tmp_path,
):
    npm_path = shutil.which("npm")
    if npm_path is None:
        pytest.skip("npm is not available")
    npm = Path(npm_path).resolve()
    repo = tmp_path / "js_repo"
    shutil.copytree(SEED, repo)
    protected_hashes = {
        path: _sha256(repo / path)
        for path in ("tests", "package.json", "package-lock.json")
    }
    python = Path(sys.executable).as_posix()
    fake = FAKE_CODEX.as_posix()
    command = [
        sys.executable,
        str(ROOT / "theustad.py"),
        "--repo",
        str(repo),
        "--task",
        str(repo / "task.md"),
        "--cmd",
        f"{python} {fake} js_honest",
        "--resume-cmd",
        f"{python} {fake} js_honest --resume {{thread_id}}",
        "--verifier",
        f'"{npm}" test',
        "--protect-add",
        "package.json",
        "package-lock.json",
        "--state-dir",
        str(tmp_path / "state"),
        "--log",
        str(tmp_path / "logs"),
        "--max-retries",
        "0",
        "--timeout",
        "30",
        "--no-color",
    ]

    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        shell=False,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert re.findall(r"^ROUND \d+ (\S+)$", result.stdout, re.MULTILINE) == [
        "VERIFIED"
    ]
    npm_result = subprocess.run(
        [str(npm), "test"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        shell=False,
    )
    assert npm_result.returncode == 0, npm_result.stdout + npm_result.stderr
    assert "pass 1" in npm_result.stdout
    assert protected_hashes == {
        path: _sha256(repo / path) for path in protected_hashes
    }
