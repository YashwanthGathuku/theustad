import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD_DISPLAY = "Ga" + "te"
OLD_LOWER = OLD_DISPLAY.lower()
OLD_UPPER = OLD_DISPLAY.upper()
OLD_NAME_RE = re.compile(
    rf"(?i:\b{re.escape(OLD_LOWER)}\b|{re.escape(OLD_LOWER)}(?:_|lib\b))"
    rf"|{re.escape(OLD_DISPLAY)}(?=[A-Z])"
)
OLD_PATH_RE = re.compile(re.escape(OLD_LOWER), re.IGNORECASE)


def legacy(text):
    return (
        text.replace("<display>", OLD_DISPLAY)
        .replace("<lower>", OLD_LOWER)
        .replace("<upper>", OLD_UPPER)
    )


def exact_lines(*entries):
    return {line_number: legacy(line) for line_number, line in entries}


HISTORY_FILES = {
    "docs/demo/README.md",
    "docs/demo/iniconfig_acceptance_test.py",
    "docs/demo/iniconfig_task.md",
    "docs/demo/prepare_wsl_demo.sh",
    legacy("docs/demo/run_<lower>_cli_wsl.sh"),
    legacy("docs/demo/run_<lower>_plugin_wsl.sh"),
    legacy("docs/demo/run_no_<lower>_wsl.sh"),
    legacy("docs/evidence/LEGACY_<upper>_EVIDENCE.md"),
    "docs/evidence/README.md",
    "docs/evidence/audit_20260720_165329.jsonl",
    "docs/evidence/live_audit_20260719_051748.jsonl",
    "docs/evidence/plugin_0_2_1_install.txt",
    "docs/evidence/plugin_0_2_install.txt",
    "docs/evidence/plugin_install.txt",
    "docs/evidence/plugin_skill_audit.txt",
    "docs/evidence/plugin_test_results.txt",
    "docs/evidence/plugin_validation.txt",
    "docs/evidence/real_project_demo/README.md",
    legacy("docs/evidence/real_project_demo/<lower>_cli_audit.jsonl"),
    legacy("docs/evidence/real_project_demo/<lower>_cli_audit.txt"),
    legacy("docs/evidence/real_project_demo/<lower>_cli_baseline_tests.txt"),
    legacy("docs/evidence/real_project_demo/<lower>_cli_console.txt"),
    legacy("docs/evidence/real_project_demo/<lower>_cli_diff.patch"),
    legacy("docs/evidence/real_project_demo/<lower>_cli_git_status.txt"),
    legacy("docs/evidence/real_project_demo/<lower>_cli_summary.txt"),
    legacy("docs/evidence/real_project_demo/<lower>_cli_tests.txt"),
    legacy("docs/evidence/real_project_demo/<lower>_plugin_audit.jsonl"),
    legacy("docs/evidence/real_project_demo/<lower>_plugin_audit.txt"),
    legacy("docs/evidence/real_project_demo/<lower>_plugin_baseline_tests.txt"),
    legacy("docs/evidence/real_project_demo/<lower>_plugin_console.jsonl"),
    legacy("docs/evidence/real_project_demo/<lower>_plugin_diff.patch"),
    legacy("docs/evidence/real_project_demo/<lower>_plugin_git_status.txt"),
    legacy("docs/evidence/real_project_demo/<lower>_plugin_list.json"),
    legacy("docs/evidence/real_project_demo/<lower>_plugin_summary.txt"),
    legacy("docs/evidence/real_project_demo/<lower>_plugin_tests.txt"),
    legacy("docs/evidence/real_project_demo/no_<lower>_console.jsonl"),
    legacy("docs/evidence/real_project_demo/no_<lower>_diff.patch"),
    legacy("docs/evidence/real_project_demo/no_<lower>_git_status.txt"),
    legacy("docs/evidence/real_project_demo/no_<lower>_summary.txt"),
    legacy("docs/evidence/real_project_demo/no_<lower>_tests.txt"),
    "docs/evidence/real_project_demo_prep.txt",
    "docs/evidence/real_project_video/README.md",
    legacy("docs/evidence/real_project_video/<lower>_plugin_audit.jsonl"),
    legacy("docs/evidence/real_project_video/<lower>_plugin_audit.txt"),
    legacy("docs/evidence/real_project_video/<lower>_plugin_baseline_tests.txt"),
    legacy("docs/evidence/real_project_video/<lower>_plugin_console.jsonl"),
    legacy("docs/evidence/real_project_video/<lower>_plugin_diff.patch"),
    legacy("docs/evidence/real_project_video/<lower>_plugin_git_status.txt"),
    legacy("docs/evidence/real_project_video/<lower>_plugin_list.json"),
    legacy("docs/evidence/real_project_video/<lower>_plugin_summary.txt"),
    legacy("docs/evidence/real_project_video/<lower>_plugin_tests.txt"),
    legacy("docs/evidence/real_project_video/no_<lower>_console.jsonl"),
    legacy("docs/evidence/real_project_video/no_<lower>_diff.patch"),
    legacy("docs/evidence/real_project_video/no_<lower>_git_status.txt"),
    legacy("docs/evidence/real_project_video/no_<lower>_summary.txt"),
    legacy("docs/evidence/real_project_video/no_<lower>_tests.txt"),
    "docs/evidence/real_project_video/video_probe.json",
    "docs/evidence/real_project_video/video_sha256.txt",
    "docs/evidence/rehearsal_console.txt",
    "docs/evidence/submission_publication.txt",
    "docs/evidence/test_results.txt",
    "docs/schema_samples.jsonl",
    legacy("docs/superpowers/plans/2026-07-20-<lower>-codex-plugin.md"),
    legacy("docs/superpowers/plans/2026-07-20-<lower>-submission-publication.md"),
    "docs/superpowers/plans/2026-07-20-theustad-core-migration.md",
    "docs/superpowers/plans/2026-07-20-theustad-demo-publication.md",
    "docs/superpowers/plans/2026-07-20-theustad-robustness-evidence.md",
    legacy("docs/superpowers/specs/2026-07-20-<lower>-codex-plugin-design.md"),
    legacy("docs/superpowers/specs/2026-07-20-<lower>-submission-value-design.md"),
    "docs/superpowers/specs/2026-07-20-theustad-release-design.md",
    "docs/video/.gitignore",
    "docs/video/README.md",
    "docs/video/build_demo.ps1",
    "docs/video/build_live_narrated_demo.ps1",
    legacy("docs/video/<lower>-real-project-live-narrated.en.srt"),
    legacy("docs/video/<lower>-real-project-live-narrated.mp4"),
    legacy("docs/video/<lower>-real-project-live.mp4"),
    legacy("docs/video/<lower>-v2-demo.mp4"),
    "docs/video/record_live_comparison.ps1",
    "docs/video/render_demo.py",
    "docs/video/run_live_comparison_wsl.sh",
}
COMPATIBILITY_PATHS = {
    legacy("compat/<lower>-plugin/.codex-plugin/plugin.json"),
    legacy("compat/<lower>-plugin/scripts/<lower>_plugin.py"),
    legacy("compat/<lower>-plugin/skills/audit/SKILL.md"),
    legacy("compat/<lower>-plugin/skills/doctor/SKILL.md"),
    legacy("compat/<lower>-plugin/skills/run/SKILL.md"),
    legacy("<lower>.py"),
    legacy("<lower>lib/__init__.py"),
    legacy("<lower>lib/chain.py"),
    legacy("<lower>lib/claims.py"),
    legacy("<lower>lib/events.py"),
    legacy("<lower>lib/freezer.py"),
    legacy("<lower>lib/session.py"),
    legacy("<lower>lib/verifier.py"),
    legacy("scripts/<lower>_plugin.py"),
    "tests/test_legacy_compat.py",
}
ALLOWED_OCCURRENCES = {
    ".codex-plugin/plugin.json": exact_lines(
        (8, '  "homepage": "https://devpost.com/software/<lower>-0lypv2",'),
        (29, '    "websiteURL": "https://devpost.com/software/<lower>-0lypv2",'),
    ),
    ".gitignore": exact_lines((6, ".<lower>-state/")),
    "NOTICE": exact_lines(
        (4, "Formerly released as <display> v2"),
        (15, "    Formerly released as <display> v2"),
    ),
    "README.md": exact_lines(
        (138, "## Legacy <display> submission evidence"),
        (140, "- Devpost: https://devpost.com/software/<lower>-0lypv2"),
        (143, "- Live real-project video: [`docs/video/<lower>-real-project-live-narrated.mp4`](docs/video/<lower>-real-project-live-narrated.mp4)"),
        (284, "## <display> 1.x compatibility"),
        (286, "<display>-named CLI, import, environment-variable, and plugin entry points are"),
        (288, "may temporarily use `<lower>.py`, `<lower>lib`, `<upper>_STATE_HOME`, `<upper>_PYTHON`, or"),
        (289, "`<lower>@personal`; new installations and documentation must use the canonical"),
        (308, "## Legacy <display> real-project recording"),
        (319, "[`narrated live recording`](docs/video/<lower>-real-project-live-narrated.mp4)"),
        (320, "shows the ordinary control run, plugin installation, live `$<lower>:run`, exact"),
        (327, "capture remains at [`docs/video/<lower>-real-project-live.mp4`](docs/video/<lower>-real-project-live.mp4)"),
        (336, "| Ordinary Codex without <display> | 51 passed | No <display> verdict, audit log, or root |"),
        (337, "| Installed <display> plugin | 50 passed | `$<lower>:run` verified, then `$<lower>:audit` validated the chain |"),
        (343, "Ordinary Codex solved the task. <display>'s demonstrated value is the protected,"),
        (398, "## Legacy <display> live Codex run"),
        (405, "python <lower>.py --repo demo_repo --task task.md"),
        (408, "<display> uses the verified CLI forms `codex exec --json --sandbox workspace-write`"),
    ),
    "docs/BUILD_EVIDENCE.md": exact_lines(
        (4, "verbatim historical evidence. Their <display>-named paths, protocol samples, roots,"),
        (5, "and outcomes are indexed in `docs/evidence/LEGACY_<upper>_EVIDENCE.md`; new"),
        (15, "  not currently satisfy SPEC section 1's WSL 2 requirement for running <display>."),
        (261, '> codex exec --json "Reply with exactly: <upper>_NON_GIT_PING"'),
        (264, '> codex exec --json --skip-git-repo-check "Reply with exactly: <upper>_NON_GIT_PING"'),
        (275, '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"<upper>_NON_GIT_PING"}}'),
        (293, r"C:\Users\Gathu\AppData\Local\Temp\<lower>-prompt0-isolated-pytest-20260717"),
        (341, '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"<upper>_SCHEMA_PING"}}'),
        (371, "therefore created `tests/__pycache__`, and <display> correctly classified that"),
        (379, "- Command: `python <lower>.py --repo demo_repo --task task.md`."),
        (383, "- Final <display> exit code: `0`."),
        (385, r"  `C:\Users\Gathu\AppData\Local\Temp\<lower>-v2-state-ovtf7_dn\logs\audit_20260719_051748.jsonl`."),
        (396, "`tests/**`; <display> recorded `TAMPERED` and restored the baseline. <display> resumed"),
        (400, "contained a character that strict Windows CP-1252 could not encode. <display> now"),
        (405, "error 5. <display> still invoked Codex with `--sandbox workspace-write`; no sandbox"),
    ),
    "docs/PLUGIN_GUIDE.md": exact_lines(
        (186, "## <display> 1.x compatibility"),
        (188, "<display>-named entry points are deprecated adapters through TheUstad 1.x. Existing"),
        (189, "automation may temporarily use `<lower>.py`, `<lower>lib`, `<upper>_STATE_HOME`,"),
        (190, "`<upper>_PYTHON`, `<lower>@personal`, and `$<lower>:*`; canonical TheUstad names take"),
    ),
    "docs/SPEC.md": exact_lines(
        (18, "derive from his `evidence-<lower>` agent-discipline work. Any public"),
        (121, "<display>-named entry points are deprecated adapters through TheUstad 1.x and are"),
        (122, "scheduled for removal in 2.0. `<lower>.py` forwards to `theustad.py`, `<lower>lib`"),
        (123, "forwards to `theustadlib`, and the optional `compat/<lower>-plugin/` package"),
        (124, "forwards to the canonical `theustad@personal` installation. `<upper>_STATE_HOME`"),
        (125, "and `<upper>_PYTHON` are accepted only when their `THEUSTAD_*` equivalents are"),
    ),
    legacy("<lower>.py"): exact_lines(
        (2, '"""Deprecated <display> entry point forwarding to TheUstad."""'),
        (10, "<display>Result = TheUstadResult"),
        (11, "<display>Runner = TheUstadRunner"),
        (15, '    print("<upper>_DEPRECATED use theustad.py", file=sys.stderr)'),
    ),
    legacy("scripts/<lower>_plugin.py"): exact_lines(
        (2, '"""Deprecated <display> plugin launcher forwarding to TheUstad."""'),
        (16, '    print("<upper>_DEPRECATED use scripts/theustad_plugin.py", file=sys.stderr)'),
    ),
    "scripts/install_plugin.py": exact_lines(
        (2, '"""Install TheUstad and any required <display> compatibility alias."""'),
        (32, 'LEGACY_PLUGIN_NAME = "<lower>"'),
        (33, 'LEGACY_PLUGIN_ID = "<lower>@personal"'),
        (243, '        help="also install the deprecated <lower>@personal forwarding package",'),
        (288, '        install_legacy_adapter(source / "compat" / "<lower>-plugin", legacy_destination)'),
        (294, '        print(f"<upper>_PLUGIN_COMPAT_INSTALLED {legacy_destination}")'),
    ),
    "scripts/theustad_plugin.py": exact_lines(
        (115, '    elif values.get("<upper>_STATE_HOME"):'),
        (116, '        warning("<upper>_DEPRECATED use THEUSTAD_STATE_HOME")'),
        (117, '        root = Path(values["<upper>_STATE_HOME"])'),
    ),
    "tests/test_events.py": exact_lines(
        (168, '    ] == ["<upper>_SCHEMA_PING"]'),
    ),
    "tests/test_plugin_launcher.py": exact_lines(
        (76, '        environ={"THEUSTAD_STATE_HOME": str(current), "<upper>_STATE_HOME": str(legacy)},'),
        (87, '        environ={"<upper>_STATE_HOME": str(legacy)}, warning=warnings.append'),
        (89, '    assert warnings == ["<upper>_DEPRECATED use THEUSTAD_STATE_HOME"]'),
    ),
    "tests/test_plugin_package.py": exact_lines(
        (61, '    assert manifest["homepage"] == "https://devpost.com/software/<lower>-0lypv2"'),
        (116, '        "Formerly released as <display> v2",'),
        (316, "def test_update_marketplace_replaces_<lower>_in_place(tmp_path):"),
        (322, '            {"name": "<lower>", "source": {"source": "local", "path": "old"}},'),
        (329, '        plugin_name="<lower>",'),
        (330, '        plugin_path=tmp_path / "plugins" / "<lower>",'),
        (336, '        "<lower>",'),
        (339, '    assert payload["plugins"][1]["source"]["path"] == "./plugins/<lower>"'),
        (391, '    assert not (home / "plugins" / "<lower>").exists()'),
        (398, "def test_installer_upgrades_existing_<lower>_to_forwarding_package(tmp_path):"),
        (400, '    legacy = home / "plugins" / "<lower>"'),
        (414, '        (["/usr/bin/codex", "plugin", "add", "<lower>@personal", "--json"], home),'),
        (427, '        "scripts/<lower>_plugin.py",'),
        (430, '    assert not (legacy / "<lower>lib").exists()'),
        (434, "def test_installer_marketplace_<lower>_entry_triggers_upgrade_and_preserves_slot(tmp_path):"),
        (439, '        [{"name": "before"}, {"name": "<lower>"}, {"name": "after"}],'),
        (453, '        "<lower>",'),
        (457, '    assert (home / "plugins" / "<lower>" / "scripts" / "<lower>_plugin.py").is_file()'),
        (477, '    assert [call[0][-2] for call in calls] == ["theustad@personal", "<lower>@personal"]'),
        (478, '    assert (home / "plugins" / "<lower>" / "scripts" / "<lower>_plugin.py").is_file()'),
        (482, '    source = ROOT / "compat" / "<lower>-plugin"'),
        (495, '            source, tmp_path / "plugins" / "<lower>"'),
        (501, '    adapter_source = ROOT / "compat" / "<lower>-plugin"'),
        (502, '    adapter = plugins / "<lower>"'),
        (508, '    module_path = adapter / "scripts" / "<lower>_plugin.py"'),
        (509, '    spec = importlib.util.spec_from_file_location("installed_<lower>_adapter", module_path)'),
        (538, '    adapter = tmp_path / "plugins" / "<lower>"'),
        (539, '    plugin_installer.install_legacy_adapter(ROOT / "compat" / "<lower>-plugin", adapter)'),
        (540, '    module_path = adapter / "scripts" / "<lower>_plugin.py"'),
        (548, '    assert "<upper>_DEPRECATED use $theustad:<command>" in captured.err'),
        (561, '    assert not (home / "plugins" / "<lower>").exists()'),
        (602, '        "docs/video/<lower>-real-project-live.mp4",'),
        (610, "def test_legacy_<lower>_demo_documents_both_interfaces_and_honesty_boundaries():"),
        (617, '        "$<lower>:doctor",'),
        (618, '        "$<lower>:run",'),
        (619, '        "$<lower>:audit",'),
        (620, '        "<lower>.py --repo",'),
        (651, '    assert "<upper>_DOCTOR_OK" in release_installation'),
        (657, '    assert "SUPPORTED_<upper>_RUN NOT RUN" in real_demo'),
    ),
    "tests/test_legacy_compat.py": exact_lines(
        (6, "import <lower>"),
        (8, "from scripts import <lower>_plugin, theustad_plugin"),
        (9, "from <lower>lib.chain import AuditChain as LegacyAuditChain"),
        (17, "    assert <lower>.<display>Runner is theustad.TheUstadRunner"),
        (18, "    assert <lower>.<display>Result is theustad.TheUstadResult"),
        (19, "    assert <lower>.Verdict is theustad.Verdict"),
        (31, '    assert "<display>Runner" not in class_names'),
        (32, '    assert "<display>Result" not in class_names'),
        (37, '        [sys.executable, str(ROOT / "<lower>.py"), "--help"],'),
        (44, '    assert "<upper>_DEPRECATED use theustad.py" in result.stderr'),
        (49, "    assert <lower>_plugin.build_theustad_argv is theustad_plugin.build_theustad_argv"),
        (54, '        [sys.executable, str(ROOT / "scripts" / "<lower>_plugin.py"), "--help"],'),
        (62, '    assert "<upper>_DEPRECATED use scripts/theustad_plugin.py" in result.stderr'),
    ),
    legacy("compat/<lower>-plugin/.codex-plugin/plugin.json"): exact_lines(
        (2, '  "name": "<lower>",'),
        (4, '  "description": "Deprecated <display> plugin alias that forwards commands to TheUstad.",'),
        (8, '  "homepage": "https://devpost.com/software/<lower>-0lypv2",'),
        (18, '    "displayName": "<display> (TheUstad compatibility)",'),
        (20, '    "longDescription": "This deprecated <display> package forwards plugin commands to the canonical TheUstad installation.",'),
        (28, '    "websiteURL": "https://devpost.com/software/<lower>-0lypv2",'),
        (30, '    "defaultPrompt": "This deprecated <display> alias forwards the command to TheUstad."'),
    ),
    legacy("compat/<lower>-plugin/scripts/<lower>_plugin.py"): exact_lines(
        (13, '    print("<upper>_DEPRECATED use $theustad:<command>", file=sys.stderr)'),
        (22, '            f"<upper>_PLUGIN_ERROR canonical TheUstad plugin launcher is missing: "'),
    ),
    legacy("compat/<lower>-plugin/skills/audit/SKILL.md"): exact_lines(
        (3, "description: Deprecated <display> alias for TheUstad audit-chain verification. Use only when the user invokes $<lower>:audit."),
        (6, "# <display> Compatibility Audit"),
        (12, "<absolute-python> <plugin-root>/scripts/<lower>_plugin.py audit <absolute-log-path>"),
    ),
    legacy("compat/<lower>-plugin/skills/doctor/SKILL.md"): exact_lines(
        (3, "description: Deprecated <display> alias for TheUstad's project prerequisite check. Use only when the user invokes $<lower>:doctor."),
        (6, "# <display> Compatibility Doctor"),
        (12, "<absolute-python> <plugin-root>/scripts/<lower>_plugin.py doctor --repo <repo>"),
    ),
    legacy("compat/<lower>-plugin/skills/run/SKILL.md"): exact_lines(
        (3, "description: Deprecated <display> alias for running a coding task through TheUstad. Use only when the user invokes $<lower>:run."),
        (6, "# <display> Compatibility Run"),
        (12, "<absolute-python> <plugin-root>/scripts/<lower>_plugin.py run --repo <repo> --task-text <task>"),
    ),
}


def tracked_files(*, root=ROOT):
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    return [os.fsdecode(relative) for relative in output.split(b"\0") if relative]


def line_is_allowed(relative, line_number, line):
    return ALLOWED_OCCURRENCES.get(relative, {}).get(line_number) == line


def find_offenders(files, *, root=ROOT):
    offenders = []
    for relative in files:
        if relative in HISTORY_FILES:
            continue

        if OLD_PATH_RE.search(relative) and relative not in COMPATIBILITY_PATHS:
            offenders.append(f"{relative}:path")

        path = root / relative
        if not path.is_file() or b"\0" in path.read_bytes()[:4096]:
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="surrogateescape").splitlines(),
            start=1,
        ):
            if OLD_NAME_RE.search(line) and not line_is_allowed(
                relative, line_number, line
            ):
                offenders.append(f"{relative}:{line_number}:{line.strip()}")
    return offenders


def test_old_product_name_is_confined_to_compatibility_and_history():
    assert find_offenders(tracked_files()) == []


def test_old_product_name_in_tracked_path_is_reported(tmp_path):
    path = tmp_path / legacy("<lower>-dashboard.md")
    path.write_text("Current product dashboard.\n", encoding="utf-8")

    assert find_offenders([path.name], root=tmp_path) == [f"{path.name}:path"]


def test_compatibility_allowance_does_not_hide_unlabelled_branding(tmp_path):
    relative = legacy("<lower>.py")
    allowed = ALLOWED_OCCURRENCES[relative]
    lines = [""] * max(allowed)
    for line_number, line in allowed.items():
        lines[line_number - 1] = line
    lines.append(legacy("<display> is the canonical product."))
    path = tmp_path / relative
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert find_offenders([path.name], root=tmp_path) == [
        f"{relative}:{len(lines)}:{lines[-1]}"
    ]


def test_new_theustad_evidence_remains_scanned(tmp_path):
    relative = legacy("docs/evidence/theustad-1.0/<lower>-dashboard.md")
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text("Current product dashboard.\n", encoding="utf-8")

    assert find_offenders([relative], root=tmp_path) == [f"{relative}:path"]


def test_all_declared_path_exceptions_exist_in_git():
    files = set(tracked_files())
    declared_files = HISTORY_FILES | COMPATIBILITY_PATHS | set(ALLOWED_OCCURRENCES)
    assert sorted(declared_files - files) == []


def test_camel_case_old_identifier_is_reported(tmp_path):
    path = tmp_path / "canonical.py"
    line = f"class {OLD_DISPLAY}Dashboard:"
    path.write_text(f"{line}\n    pass\n", encoding="utf-8")

    assert find_offenders([path.name], root=tmp_path) == [
        f"canonical.py:1:{line}"
    ]


def test_non_ascii_tracked_path_is_decoded_and_reported(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    path = tmp_path / f"caf\u00e9-{OLD_LOWER}-dashboard.md"
    path.write_text("Current product dashboard.\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", path.name], cwd=tmp_path, check=True)

    files = tracked_files(root=tmp_path)
    assert files == [path.name]
    assert find_offenders(files, root=tmp_path) == [f"{path.name}:path"]


def test_allowed_token_with_unrelated_branding_is_reported(tmp_path):
    relative = "tests/test_plugin_launcher.py"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    line = (
        f'environ={{"{OLD_UPPER}_STATE_HOME": "x"}}  '
        f"# {OLD_DISPLAY} is canonical"
    )
    path.write_text(f"{line}\n", encoding="utf-8")

    assert find_offenders([relative], root=tmp_path) == [f"{relative}:1:{line}"]


def test_formerly_allowed_function_does_not_hide_branding(tmp_path):
    relative = "tests/test_plugin_package.py"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    function_line = ALLOWED_OCCURRENCES[relative][316]
    line = f'    message = "{OLD_DISPLAY} is canonical"'
    path.write_text(
        ("\n" * 315)
        + f"{function_line}\n"
        f"{line}\n",
        encoding="utf-8",
    )

    assert find_offenders([relative], root=tmp_path) == [
        f"{relative}:317:{line.strip()}"
    ]


def test_rule_definition_region_does_not_hide_branding(tmp_path):
    relative = "tests/test_active_naming.py"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    line = f"{OLD_DISPLAY} is canonical"
    path.write_text(
        "# naming-audit: rule-definitions-start\n"
        f"{line}\n"
        "# naming-audit: rule-definitions-end\n",
        encoding="utf-8",
    )

    assert find_offenders([relative], root=tmp_path) == [f"{relative}:2:{line}"]
