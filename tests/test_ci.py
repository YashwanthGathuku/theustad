"""CI mode: judge a finished change with the tests it started from."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from theustadlib import ci
from theustadlib.freezer import check, freeze_commit


ROOT = Path(__file__).resolve().parents[1]
THEUSTAD = ROOT / "theustad.py"
VERIFY_CHAIN = ROOT / "verify_chain.py"
DEMO = ROOT / "demo_repo"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "TheUstad Test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "TheUstad Test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}

sys.path.insert(0, str(ROOT))
import fake_codex  # noqa: E402  (the scripted demo's honest repair)


def git(repo, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ, **GIT_ENV},
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path):
    """The demo project committed on ``main``, with ``agent`` checked out."""
    project = tmp_path / "project"
    shutil.copytree(
        DEMO,
        project,
        ignore=shutil.ignore_patterns(
            "__pycache__", ".pytest_cache", ".theustad_fake_codex_state.json"
        ),
    )
    git(project, "init", "-q", "-b", "main")
    git(project, "config", "core.autocrlf", "false")
    commit_all(project, "base")
    git(project, "switch", "-q", "-c", "agent")
    return project


def honest_fix(repo):
    fake_codex._apply_naive_parser_fix(repo)
    fake_codex._apply_proper_invoice_fix(repo)


def run(repo, tmp_path, **options):
    lines = []
    options.setdefault("ephemeral", True)
    result = ci.run_check(
        repo,
        "main",
        state_dir=tmp_path / "state",
        output=lines.append,
        **options,
    )
    return result, lines


def test_honest_change_is_verified(repo, tmp_path):
    honest_fix(repo)
    commit_all(repo, "fix")

    result, lines = run(repo, tmp_path)

    assert result.verdict is ci.CIVerdict.VERIFIED
    assert result.exit_code == 0
    assert result.census_armed and result.census_tests == 11
    assert "FINAL VERIFIED" in lines


def test_unrepaired_change_is_falsified(repo, tmp_path):
    (repo / "app" / "notes.py").write_text("# nothing fixed\n", encoding="utf-8")
    commit_all(repo, "no fix")

    result, _ = run(repo, tmp_path)

    assert result.verdict is ci.CIVerdict.FALSIFIED
    assert result.exit_code == 1


def test_edited_test_is_tampered_and_judged_by_the_original(repo, tmp_path):
    test_file = repo / "tests" / "test_parser.py"
    test_file.write_text(
        test_file.read_text(encoding="utf-8").replace(
            'assert parse_duration("90m") == 5400', "assert True"
        ),
        encoding="utf-8",
    )
    commit_all(repo, "weaken")

    result, lines = run(repo, tmp_path)

    assert result.verdict is ci.CIVerdict.TAMPERED
    assert result.changes.modified == ("tests/test_parser.py",)
    # The verifier ran against the restored test, so the real failure shows.
    assert result.verification.exit_code != 0
    assert "CHANGED_PROTECTED modified tests/test_parser.py" in lines


def test_deleted_test_is_tampered(repo, tmp_path):
    honest_fix(repo)
    (repo / "tests" / "test_invoice.py").unlink()
    commit_all(repo, "drop the inconvenient test")

    result, _ = run(repo, tmp_path)

    assert result.verdict is ci.CIVerdict.TAMPERED
    assert result.changes.deleted == ("tests/test_invoice.py",)


def test_new_test_is_excluded_rather_than_convicted(repo, tmp_path):
    honest_fix(repo)
    (repo / "tests" / "test_more.py").write_text(
        "from app.parser import parse_duration\n\n"
        "def test_120m():\n    assert parse_duration('120m') == 7200\n",
        encoding="utf-8",
    )
    commit_all(repo, "fix with a new test")

    result, lines = run(repo, tmp_path)

    assert result.verdict is ci.CIVerdict.VERIFIED
    assert result.changes.added == ("tests/test_more.py",)
    assert any(line.startswith("EXCLUDED") for line in lines)


@pytest.mark.parametrize("census_enabled", [None, False])
def test_planted_conftest_is_removed_before_verifying(repo, tmp_path, census_enabled):
    (repo / "tests" / "conftest.py").write_text(
        'collect_ignore_glob = ["test_parser.py", "test_invoice.py"]\n',
        encoding="utf-8",
    )
    commit_all(repo, "hide the failing tests")

    result, _ = run(repo, tmp_path, census_enabled=census_enabled)

    assert result.verdict is ci.CIVerdict.FALSIFIED
    assert result.changes.added == ("tests/conftest.py",)


def hide_invoice_tests(repo):
    """The reward hack the census exists for: fix the parser the easy way, which
    breaks invoicing, then skip the invoice tests from source no rule protects."""
    fake_codex._apply_naive_parser_fix(repo)
    with (repo / "app" / "invoice.py").open("a", encoding="utf-8") as source:
        source.write("\nimport pytest\npytest.skip('x', allow_module_level=True)\n")


def test_module_level_skip_in_source_is_caught_by_the_census(repo, tmp_path):
    hide_invoice_tests(repo)
    commit_all(repo, "skip from source")

    result, _ = run(repo, tmp_path)

    assert result.verdict is ci.CIVerdict.FALSIFIED
    assert result.census_result.reason in (ci.census.CENSUS_SHRINK, ci.census.CENSUS_SKIP)


def test_exit_on_import_is_caught_by_the_census(repo, tmp_path):
    exit_on_import(repo)
    commit_all(repo, "exit before any assertion")

    result, _ = run(repo, tmp_path)

    assert result.verification.exit_code == 0
    assert result.verdict is ci.CIVerdict.FALSIFIED
    assert result.census_result.reason == ci.census.REPORT_MISSING


def exit_on_import(repo):
    with (repo / "app" / "parser.py").open("a", encoding="utf-8") as source:
        source.write("\nimport os\nos._exit(0)\n")


@pytest.mark.parametrize(
    "attack", [hide_invoice_tests, exit_on_import], ids=["module-level-skip", "exit-on-import"]
)
def test_without_the_census_both_attacks_pass(repo, tmp_path, attack):
    # The counterpart of the two census tests above: it is the census, not
    # the verifier's exit code, that catches them.
    attack(repo)
    commit_all(repo, "attack")

    result, _ = run(repo, tmp_path, census_enabled=False)

    assert result.verdict is ci.CIVerdict.VERIFIED


def test_tampering_while_the_tests_run_is_caught(repo, tmp_path):
    honest_fix(repo)
    with (repo / "app" / "parser.py").open("a", encoding="utf-8") as source:
        source.write(
            "\nfrom pathlib import Path as _P\n"
            "_P(__file__).resolve().parents[1].joinpath("
            "'tests', 'test_parser.py').write_text('', encoding='utf-8')\n"
        )
    commit_all(repo, "edit the tests from the code under test")

    result, _ = run(repo, tmp_path, census_enabled=False)

    assert result.verdict is ci.CIVerdict.TAMPERED
    assert result.changes.tampered is False
    assert result.verifier_time_tampering.modified == ["tests/test_parser.py"]


def test_policy_comes_from_the_base_commit(repo, tmp_path):
    git(repo, "switch", "-q", "main")
    (repo / ".theustad.json").write_text(
        json.dumps({"verifier": "python -m pytest -q tests/test_parser.py"}),
        encoding="utf-8",
    )
    commit_all(repo, "policy")
    git(repo, "switch", "-q", "agent")
    git(repo, "rebase", "-q", "main")
    (repo / ".theustad.json").write_text('{"verifier": "true"}', encoding="utf-8")
    commit_all(repo, "weaken the policy")

    result, _ = run(repo, tmp_path, census_enabled=False)

    assert result.policy.verifier_argv[-1] == "tests/test_parser.py"
    assert result.verdict is ci.CIVerdict.TAMPERED
    assert ".theustad.json" in result.changes.modified


def test_unknown_policy_key_fails_closed(repo, tmp_path):
    git(repo, "switch", "-q", "main")
    (repo / ".theustad.json").write_text('{"verfier": "true"}', encoding="utf-8")
    commit_all(repo, "typo")
    git(repo, "switch", "-q", "agent")
    git(repo, "rebase", "-q", "main")

    with pytest.raises(ValueError, match="unknown keys: verfier"):
        run(repo, tmp_path)


def test_working_tree_is_put_back_unless_ephemeral(repo, tmp_path):
    test_file = repo / "tests" / "test_parser.py"
    test_file.write_text("def test_nothing():\n    pass\n", encoding="utf-8")
    commit_all(repo, "weaken")
    (repo / "tests" / "wip_notes.txt").write_text("mine\n", encoding="utf-8")
    before = {
        path.relative_to(repo).as_posix(): path.read_bytes()
        for path in (repo / "tests").rglob("*")
        if path.is_file()
    }

    result, _ = run(repo, tmp_path, ephemeral=False)

    after = {
        path.relative_to(repo).as_posix(): path.read_bytes()
        for path in (repo / "tests").rglob("*")
        if path.is_file()
    }
    assert result.verdict is ci.CIVerdict.TAMPERED
    assert after == before


def test_shallow_history_says_how_to_fix_it(repo, tmp_path):
    honest_fix(repo)
    commit_all(repo, "fix")
    clone = tmp_path / "shallow"
    git(
        tmp_path,
        "clone",
        "-q",
        "--depth",
        "1",
        "--branch",
        "agent",
        repo.resolve().as_uri(),
        str(clone),
    )
    git(clone, "fetch", "-q", "--depth", "1", "origin", "main:main")

    with pytest.raises(ValueError, match="fetch-depth: 0"):
        run(clone, tmp_path)


def test_option_shaped_reference_is_refused(repo, tmp_path):
    with pytest.raises(ValueError, match="not a commit reference"):
        ci.run_check(repo, "--output=/tmp/x", state_dir=tmp_path / "s", output=lambda _: None)


def test_cli_writes_json_summary_and_a_valid_audit_chain(repo, tmp_path):
    honest_fix(repo)
    commit_all(repo, "fix")
    report = tmp_path / "result.json"
    summary = tmp_path / "summary.md"

    completed = subprocess.run(
        [
            sys.executable,
            str(THEUSTAD),
            "ci",
            "--repo",
            str(repo),
            "--base",
            "main",
            "--ephemeral",
            "--state-dir",
            str(tmp_path / "state"),
            "--json",
            str(report),
            "--summary",
            str(summary),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["verdict"] == "VERIFIED"
    assert data["census"] == {
        "armed": True,
        "tests": 11,
        "detail": "",
        "reason": None,
        "missing": [],
    }
    assert summary.read_text(encoding="utf-8").startswith("## TheUstad VERIFIED")
    oracle = subprocess.run(
        [sys.executable, str(VERIFY_CHAIN), data["audit"]["log"]],
        capture_output=True,
        text=True,
        check=False,
    )
    assert oracle.returncode == 0, oracle.stdout
    assert data["audit"]["root"] in oracle.stdout


def test_cli_reports_errors_with_exit_two(repo, tmp_path):
    completed = subprocess.run(
        [sys.executable, str(THEUSTAD), "ci", "--repo", str(repo), "--base", "no-such-ref"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "THEUSTAD_ERROR" in completed.stderr


def test_commit_snapshot_matches_a_clean_checkout(repo, tmp_path):
    manifest = freeze_commit(repo, "HEAD", ci.CI_PATTERNS, tmp_path / "state")

    assert "tests" in manifest.entries
    assert manifest.entries["tests"].file_type == "directory"
    assert check(repo, manifest).clean


@pytest.mark.skipif(os.name != "posix", reason="git symlinks need POSIX")
def test_commit_snapshot_refuses_a_protected_symlink(repo, tmp_path):
    os.symlink("test_parser.py", repo / "tests" / "test_alias.py")
    commit_all(repo, "symlink")

    with pytest.raises(ValueError, match="symlink"):
        freeze_commit(repo, "HEAD", ci.CI_PATTERNS, tmp_path / "state")


ACTION_SCRIPT = ROOT / "ci" / "action.sh"
posix_only = pytest.mark.skipif(
    os.name != "posix" or shutil.which("bash") is None,
    reason="the composite action's script runs under bash",
)


def run_action(repo, tmp_path, **inputs):
    outputs = tmp_path / "github_output"
    summary = tmp_path / "step_summary.md"
    environment = {
        **os.environ,
        "GITHUB_ACTION_PATH": str(ROOT),
        "GITHUB_WORKSPACE": str(repo),
        "GITHUB_OUTPUT": str(outputs),
        "GITHUB_STEP_SUMMARY": str(summary),
        "RUNNER_TEMP": str(tmp_path / "runner_temp"),
        "THEUSTAD_PYTHON": sys.executable,
        "THEUSTAD_BASE": "main",
    }
    environment.update(inputs)
    completed = subprocess.run(
        ["bash", str(ACTION_SCRIPT)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    values = {}
    if outputs.exists():
        for line in outputs.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            values[key] = value
    return completed, values, summary


@posix_only
def test_action_verifies_an_honest_change(repo, tmp_path):
    honest_fix(repo)
    commit_all(repo, "fix")

    completed, outputs, summary = run_action(repo, tmp_path)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert outputs["verdict"] == "VERIFIED"
    assert Path(outputs["audit-log"]).is_file()
    assert summary.read_text(encoding="utf-8").startswith("## TheUstad VERIFIED")


@posix_only
def test_action_fails_a_change_that_edits_its_tests(repo, tmp_path):
    (repo / "tests" / "test_parser.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    commit_all(repo, "weaken")

    completed, outputs, _ = run_action(repo, tmp_path)

    assert completed.returncode == 1
    assert outputs["verdict"] == "TAMPERED"


def _pull_request_event(repo):
    """What GitHub reports for this pull request, which its workflow cannot set.

    The checkout here is the pull request's head; on GitHub the default is a
    merge commit, reported as ``github.sha``. Either is accepted.
    """
    return {
        "THEUSTAD_EVENT_BASE": git(repo, "rev-parse", "main"),
        "THEUSTAD_EVENT_HEAD": git(repo, "rev-parse", "HEAD"),
        "THEUSTAD_EVENT_SHA": "0" * 40,
    }


@posix_only
@pytest.mark.parametrize("named_base", ["HEAD", "agent", ""])
def test_a_pull_request_cannot_choose_its_own_baseline(repo, tmp_path, named_base):
    # GitHub runs the pull request's own copy of the workflow, so `base:
    # HEAD` there would make the change its own baseline: nothing would
    # differ from it, and weakened tests would verify.
    (repo / "tests" / "test_parser.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    commit_all(repo, "weaken")

    completed, outputs, _ = run_action(
        repo, tmp_path, THEUSTAD_BASE=named_base, **_pull_request_event(repo)
    )

    assert outputs["verdict"] == "TAMPERED", completed.stdout + completed.stderr
    assert completed.returncode == 1
    assert ("ignoring the 'base' input" in completed.stderr) == bool(named_base)


@posix_only
def test_a_pull_request_check_must_check_out_the_pull_request(repo, tmp_path):
    # A workflow that checks out the base branch instead would judge code the
    # pull request does not contain, and pass it.
    (repo / "tests" / "test_parser.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    commit_all(repo, "weaken")
    event = _pull_request_event(repo)
    git(repo, "switch", "-q", "main")

    completed, outputs, _ = run_action(repo, tmp_path, **event)

    assert completed.returncode == 2
    assert "neither the pull request's merge commit" in completed.stderr
    assert outputs == {}


def _weaken_then_restore(repo):
    """A pull request weakens a test; a later workflow step puts it back."""
    test = repo / "tests" / "test_parser.py"
    original = test.read_text(encoding="utf-8")
    test.write_text("def test_ok():\n    pass\n", encoding="utf-8")
    commit_all(repo, "weaken")
    event = _pull_request_event(repo)
    test.write_text(original, encoding="utf-8")
    honest_fix(repo)
    return event


@posix_only
def test_a_step_before_the_check_cannot_commit_a_tree_to_be_judged(repo, tmp_path):
    # The synthetic commit descends from the pull request's head, so asking
    # only whether the head is an ancestor would accept it.
    event = _weaken_then_restore(repo)
    commit_all(repo, "passing tree")

    completed, outputs, _ = run_action(repo, tmp_path, **event)

    assert completed.returncode == 2
    assert "neither the pull request's merge commit" in completed.stderr
    assert outputs == {}


@posix_only
def test_a_step_before_the_check_cannot_rewrite_the_files_it_judges(repo, tmp_path):
    # The pull request carries no fix; a step writes one to disk without
    # committing it. The tests run against the disk, so the change would be
    # judged by code it does not contain.
    event = _pull_request_event(repo)
    honest_fix(repo)

    completed, outputs, _ = run_action(repo, tmp_path, **event)

    assert completed.returncode == 2
    assert "tracked files differ" in completed.stderr
    assert outputs == {}


@posix_only
def test_a_step_before_the_check_cannot_add_files_it_judges(repo, tmp_path):
    event = _pull_request_event(repo)
    (repo / "app" / "supplied.py").write_text("VALUE = 1\n", encoding="utf-8")

    completed, outputs, _ = run_action(repo, tmp_path, **event)

    assert completed.returncode == 2
    assert "untracked files are in the checkout, first app/supplied.py" in completed.stderr
    assert outputs == {}


@posix_only
def test_a_step_before_the_check_cannot_restore_what_the_pull_request_deleted(
    repo, tmp_path
):
    # The pull request deletes an implementation and ignores its path; a
    # step writes the implementation back, where git status cannot see it.
    honest_fix(repo)
    invoice = repo / "app" / "invoice.py"
    implementation = invoice.read_text(encoding="utf-8")
    invoice.unlink()
    with (repo / ".gitignore").open("a", encoding="utf-8") as ignore:
        ignore.write("app/invoice.py\n")
    commit_all(repo, "delete the implementation")
    event = _pull_request_event(repo)
    invoice.write_text(implementation, encoding="utf-8")

    completed, outputs, _ = run_action(repo, tmp_path, **event)

    assert completed.returncode == 2
    assert "app/invoice.py is deleted by the pull request" in completed.stderr
    assert outputs == {}


@posix_only
@pytest.mark.parametrize("flag", ["--skip-worktree", "--assume-unchanged"])
def test_index_flags_cannot_hide_a_rewritten_file(repo, tmp_path, flag):
    # Code a step runs before the check can mark tracked files as unchanged
    # in the repository's own index; its `git status` then reports nothing.
    event = _pull_request_event(repo)
    git(repo, "update-index", flag, "app/parser.py", "app/invoice.py")
    honest_fix(repo)
    assert git(repo, "status", "--porcelain") == ""

    completed, outputs, _ = run_action(repo, tmp_path, **event)

    assert completed.returncode == 2
    assert "tracked files differ from the pull request's commit, first app/" in completed.stderr
    assert outputs == {}


@posix_only
def test_the_repository_exclude_file_cannot_hide_an_added_file(repo, tmp_path):
    event = _pull_request_event(repo)
    with (repo / ".git" / "info" / "exclude").open("a", encoding="utf-8") as exclude:
        exclude.write("app/supplied.py\n")
    (repo / "app" / "supplied.py").write_text("VALUE = 1\n", encoding="utf-8")

    completed, outputs, _ = run_action(repo, tmp_path, **event)

    assert completed.returncode == 2
    assert "first app/supplied.py" in completed.stderr


@posix_only
def test_an_untracked_gitignore_cannot_hide_itself(repo, tmp_path):
    event = _pull_request_event(repo)
    (repo / "app" / ".gitignore").write_text("*\n", encoding="utf-8")
    (repo / "app" / "supplied.py").write_text("VALUE = 1\n", encoding="utf-8")

    completed, outputs, _ = run_action(repo, tmp_path, **event)

    assert completed.returncode == 2
    assert "first app/.gitignore" in completed.stderr


@posix_only
def test_a_replace_ref_cannot_change_what_head_contains(repo, tmp_path):
    # `git replace` leaves HEAD's id alone but makes git read another
    # commit's tree for it -- here the base's, where the tests are intact.
    honest_fix(repo)
    (repo / "tests" / "test_parser.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    commit_all(repo, "fix, and weaken a test")
    event = _pull_request_event(repo)
    git(repo, "replace", "HEAD", "main")

    completed, outputs, _ = run_action(repo, tmp_path, **event)

    assert outputs["verdict"] == "TAMPERED", completed.stdout + completed.stderr


@posix_only
def test_ignored_build_output_is_still_allowed(repo, tmp_path):
    honest_fix(repo)
    with (repo / ".gitignore").open("a", encoding="utf-8") as ignore:
        ignore.write("build/\n")
    commit_all(repo, "fix")
    event = _pull_request_event(repo)
    (repo / "build").mkdir()
    (repo / "build" / "output.txt").write_text("built\n", encoding="utf-8")

    completed, outputs, _ = run_action(repo, tmp_path, **event)

    assert outputs["verdict"] == "VERIFIED", completed.stdout + completed.stderr


@posix_only
def test_the_merge_commit_github_reports_is_judged(repo, tmp_path):
    honest_fix(repo)
    commit_all(repo, "fix")
    event = {**_pull_request_event(repo), "THEUSTAD_EVENT_HEAD": "f" * 40}
    event["THEUSTAD_EVENT_SHA"] = git(repo, "rev-parse", "HEAD")

    completed, outputs, _ = run_action(repo, tmp_path, **event)

    assert outputs["verdict"] == "VERIFIED", completed.stdout + completed.stderr


@posix_only
def test_action_requires_a_base(repo, tmp_path):
    completed, outputs, _ = run_action(repo, tmp_path, THEUSTAD_BASE="")

    assert completed.returncode == 2
    assert "::error" in completed.stderr
    assert outputs == {}


@posix_only
def test_action_inputs_never_become_shell(repo, tmp_path):
    honest_fix(repo)
    commit_all(repo, "fix")

    completed, outputs, _ = run_action(
        repo, tmp_path, THEUSTAD_VERIFIER="$(touch pwned) `touch pwned`"
    )

    assert completed.returncode == 2
    assert outputs["verdict"] == "ERROR"
    assert not (tmp_path / "pwned").exists()
    assert not (repo / "pwned").exists()


@posix_only
def test_action_passes_protected_patterns_literally(repo, tmp_path):
    honest_fix(repo)
    commit_all(repo, "fix")
    (tmp_path / "decoy.ini").write_text("", encoding="utf-8")

    _, outputs, _ = run_action(
        repo, tmp_path, THEUSTAD_PROTECT_ADD="app/** *.ini", THEUSTAD_CENSUS="false"
    )

    result = json.loads(Path(outputs["result"]).read_text(encoding="utf-8"))
    assert {"app/**", "*.ini"} <= set(result["policy"]["patterns"])
    assert "decoy.ini" not in result["policy"]["patterns"]
    # The honest fix edits app/, which this policy now protects.
    assert result["verdict"] == "TAMPERED"


def test_action_definition_wires_every_input_the_script_reads():
    definition = (ROOT / "action.yml").read_text(encoding="utf-8")
    script = ACTION_SCRIPT.read_text(encoding="utf-8")

    assert 'run: bash "$GITHUB_ACTION_PATH/ci/action.sh"' in definition
    read_by_script = set(
        part.split("}")[0].split(":")[0]
        for part in script.split("${")[1:]
        if part.startswith("THEUSTAD_")
    )
    from_event = {
        "THEUSTAD_EVENT_BASE": "github.event.pull_request.base.sha",
        "THEUSTAD_EVENT_HEAD": "github.event.pull_request.head.sha",
        "THEUSTAD_EVENT_SHA": "github.sha",
    }
    assert read_by_script == {
        "THEUSTAD_BASE",
        "THEUSTAD_PYTHON",
        "THEUSTAD_VERIFIER",
        "THEUSTAD_PROTECT_ADD",
        "THEUSTAD_CENSUS",
        "THEUSTAD_TIMEOUT",
        *from_event,
    }
    for name in read_by_script - set(from_event):
        assert f"        {name}: ${{{{ inputs." in definition
    # What to compare on a pull request comes from GitHub's event alone,
    # never from an input the pull request's own workflow can set.
    for name, expression in from_event.items():
        assert f"        {name}: ${{{{ {expression} }}}}\n" in definition
    # Inputs must reach the script through env, never through the run line.
    assert "${{ inputs." not in definition.split("run:", 1)[1]
