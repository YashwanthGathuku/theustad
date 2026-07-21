from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.build_plugin_assets as plugin_assets
from scripts.build_plugin_assets import build_assets
from scripts.install_plugin import (
    InstallError,
    copy_plugin,
    main as install_main,
    update_marketplace,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / ".codex-plugin" / "plugin.json"
SKILL_NAMES = ("run", "doctor", "audit")


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_manifest_identifies_theustad_and_only_bundles_skills():
    manifest = load_manifest()

    assert manifest["name"] == "theustad"
    assert re.fullmatch(r"1\.0\.0\+codex\.[a-z0-9-]+", manifest["version"])
    assert manifest["skills"] == "./skills/"
    assert manifest["license"] == "GPL-3.0-or-later"
    assert {"hooks", "mcpServers", "apps"}.isdisjoint(manifest)


def test_manifest_metadata_and_asset_paths_exist():
    manifest = load_manifest()
    interface = manifest["interface"]

    assert interface["displayName"] == "TheUstad"
    assert interface["category"] == "Developer Tools"
    assert interface["defaultPrompt"] == (
        "Run this coding task through TheUstad and report the exact verdict "
        "and audit root."
    )
    assert manifest["repository"] == "https://github.com/YashwanthGathuku/theustad"
    assert manifest["homepage"] == "https://github.com/YashwanthGathuku/theustad"
    for field in ("composerIcon", "logo"):
        value = interface[field]
        assert value.startswith("./assets/")
        assert (ROOT / value).is_file()


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_each_skill_has_frontmatter_and_launcher_command(name):
    text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")

    assert text.startswith("---\n")
    assert f"name: {name}\n" in text
    assert "description:" in text.split("---", 2)[1]
    assert "TheUstad" in text
    assert "scripts/theustad_plugin.py" in text
    assert "absolute" in text.lower()


def test_run_skill_preserves_theustad_as_the_verdict_authority():
    text = (ROOT / "skills" / "run" / "SKILL.md").read_text(encoding="utf-8")

    assert "Do not edit the target repository" in text
    assert "FINAL VERIFIED" in text
    assert "exit code 0" in text
    assert "Do not reinterpret" in text
    assert "separate TheUstad-controlled child" in text
    assert "$theustad:run" in text


def test_doctor_skill_relays_current_theustad_output_identifiers():
    text = (ROOT / "skills" / "doctor" / "SKILL.md").read_text(encoding="utf-8")

    assert "THEUSTAD_DOCTOR_*" in text
    assert "THEUSTAD_PLUGIN_ERROR" in text


def test_generated_png_assets_have_expected_dimensions(tmp_path):
    build_assets(tmp_path)

    assert plugin_assets.THEUSTAD_GREEN == (20, 184, 110, 255)
    assert png_dimensions(tmp_path / "icon.png") == (128, 128)
    assert png_dimensions(tmp_path / "logo.png") == (512, 512)


def test_committed_png_assets_have_expected_dimensions():
    assert png_dimensions(ROOT / "assets" / "icon.png") == (128, 128)
    assert png_dimensions(ROOT / "assets" / "logo.png") == (512, 512)


def test_notice_identifies_theustad_and_preserves_required_attribution():
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")

    for required in (
        "TheUstad 1.0 - originally developed by Yashwanth Gathuku",
        "https://github.com/YashwanthGathuku/theustad",
        "GPLv3 section 7(b)",
    ):
        assert required in notice


def test_official_plugin_validator_accepts_package():
    configured = os.environ.get("THEUSTAD_PLUGIN_VALIDATOR")
    validator = (
        Path(configured)
        if configured
        else Path.home()
        / ".codex"
        / "skills"
        / ".system"
        / "plugin-creator"
        / "scripts"
        / "validate_plugin.py"
    )
    if not validator.is_file() or importlib.util.find_spec("yaml") is None:
        pytest.skip("Codex plugin validator or its PyYAML dependency is not installed")

    result = subprocess.run(
        [sys.executable, str(validator), str(ROOT)],
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Plugin validation passed" in result.stdout


def write_marketplace(path: Path, plugins: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "name": "personal",
                "interface": {"displayName": "Personal"},
                "plugins": plugins,
                "custom": {"preserve": True},
            }
        ),
        encoding="utf-8",
    )


def test_copy_plugin_uses_allowlist_and_excludes_repo_and_cache_content(tmp_path):
    destination = tmp_path / "home" / "plugins" / "theustad"

    copy_plugin(ROOT, destination)

    assert (destination / "theustad.py").is_file()
    assert (destination / "theustadlib" / "session.py").is_file()
    assert (destination / "skills" / "run" / "SKILL.md").is_file()
    assert (destination / "LICENSE").is_file()
    assert (destination / "NOTICE").is_file()
    notice = (destination / "NOTICE").read_text(encoding="utf-8")
    assert "GPLv3 section 7(b)" in notice
    assert "originally developed by Yashwanth Gathuku" in notice
    assert not (destination / ".git").exists()
    assert not (destination / "tests").exists()
    assert not list(destination.rglob("__pycache__"))
    assert not list(destination.rglob("*.pyc"))


def test_copy_plugin_replaces_stale_destination_content(tmp_path):
    destination = tmp_path / "home" / "plugins" / "theustad"
    destination.mkdir(parents=True)
    (destination / ".mcp.json").write_text("{}", encoding="utf-8")

    copy_plugin(ROOT, destination)

    assert not (destination / ".mcp.json").exists()
    assert (destination / ".codex-plugin" / "plugin.json").is_file()


def test_copy_plugin_replaces_destination_symlink_without_following_it(tmp_path):
    victim = tmp_path / "victim"
    victim.mkdir()
    marker = victim / "keep.txt"
    marker.write_text("do not delete", encoding="utf-8")
    destination = tmp_path / "plugins" / "theustad"
    destination.parent.mkdir()
    try:
        destination.symlink_to(victim, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlinks unavailable: {error}")

    copy_plugin(ROOT, destination)

    assert marker.read_text(encoding="utf-8") == "do not delete"
    assert destination.is_dir()
    assert not destination.is_symlink()
    assert (destination / ".codex-plugin" / "plugin.json").is_file()


def test_copy_plugin_does_not_resolve_final_destination_component(
    tmp_path, monkeypatch
):
    destination = tmp_path / "plugins" / "theustad"
    destination.parent.mkdir()
    original_resolve = Path.resolve

    def guarded_resolve(path, *args, **kwargs):
        if path == destination:
            raise AssertionError("final destination component was resolved")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", guarded_resolve)

    copy_plugin(ROOT, destination)

    assert (destination / ".codex-plugin" / "plugin.json").is_file()


def test_copy_plugin_rejects_symlinked_package_entry(tmp_path, monkeypatch):
    destination = tmp_path / "plugins" / "theustad"
    symlinked_entry = ROOT / "theustad.py"
    original_is_symlink = Path.is_symlink

    def fake_is_symlink(path):
        if path == symlinked_entry:
            return True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    with pytest.raises(InstallError, match="symlink"):
        copy_plugin(ROOT, destination)


def test_copy_plugin_rejects_source_without_theustad_manifest(tmp_path):
    source = tmp_path / "empty"
    source.mkdir()

    with pytest.raises(InstallError, match="plugin.json"):
        copy_plugin(source, tmp_path / "plugins" / "theustad")


def test_copy_plugin_preserves_existing_install_when_source_is_incomplete(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in (
        ".codex-plugin",
        "skills",
        "scripts",
        "assets",
        "theustad.py",
        "theustadlib",
        "verify_chain.py",
        "LICENSE",
        "README.md",
    ):
        original = ROOT / name
        destination = source / name
        if original.is_dir():
            shutil.copytree(original, destination)
        else:
            shutil.copy2(original, destination)

    installed = tmp_path / "home" / "plugins" / "theustad"
    installed.mkdir(parents=True)
    marker = installed / "working-install.txt"
    marker.write_text("preserve", encoding="utf-8")

    with pytest.raises(InstallError, match="NOTICE"):
        copy_plugin(source, installed)

    assert marker.read_text(encoding="utf-8") == "preserve"


def test_update_marketplace_preserves_unrelated_plugins_and_top_level_keys(tmp_path):
    path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    other = {
        "name": "other",
        "source": {"source": "local", "path": "./plugins/other"},
    }
    write_marketplace(path, [other])

    update_marketplace(
        path,
        plugin_name="theustad",
        plugin_path=tmp_path / "plugins" / "theustad",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["custom"] == {"preserve": True}
    assert [entry["name"] for entry in payload["plugins"]] == ["other", "theustad"]
    theustad = payload["plugins"][1]
    assert theustad["source"] == {
        "source": "local",
        "path": "./plugins/theustad",
    }
    assert theustad["policy"]["installation"] == "AVAILABLE"


def test_update_marketplace_rejects_symlinked_manifest(tmp_path, monkeypatch):
    path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    plugin_path = tmp_path / "plugins" / "theustad"
    original_is_symlink = Path.is_symlink

    def fake_is_symlink(candidate):
        if candidate == path:
            return True
        return original_is_symlink(candidate)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    with pytest.raises(InstallError, match="symlink"):
        update_marketplace(path, plugin_name="theustad", plugin_path=plugin_path)


def test_update_marketplace_rejects_path_for_a_different_plugin(tmp_path):
    path = tmp_path / ".agents" / "plugins" / "marketplace.json"

    with pytest.raises(InstallError, match="theustad"):
        update_marketplace(
            path,
            plugin_name="theustad",
            plugin_path=tmp_path / "plugins" / "other",
        )


def test_installer_invokes_codex_plugin_add_with_argv(tmp_path):
    home = tmp_path / "home"
    calls = []

    def process_runner(argv, cwd):
        calls.append((argv, cwd))
        return 0

    result = install_main(
        ["--source", str(ROOT), "--home", str(home)],
        process_runner=process_runner,
        which=lambda name: "/usr/bin/codex" if name == "codex" else None,
    )

    assert result == 0
    assert calls == [
        (
            ["/usr/bin/codex", "plugin", "add", "theustad@personal", "--json"],
            home,
        )
    ]
    assert (home / "plugins" / "theustad" / "theustad.py").is_file()
    marketplace = json.loads(
        (home / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    assert marketplace["plugins"][0]["name"] == "theustad"


def test_installer_missing_codex_does_not_change_plugin_state(tmp_path):
    home = tmp_path / "home"

    result = install_main(
        ["--source", str(ROOT), "--home", str(home)],
        which=lambda name: None,
    )

    assert result == 2
    assert not (home / "plugins" / "theustad").exists()
    assert not (home / ".agents" / "plugins" / "marketplace.json").exists()


def test_readme_documents_complete_plugin_workflow_and_platform_boundary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for required in (
        "## Codex plugin",
        '"$THEUSTAD_PYTHON" scripts/install_plugin.py',
        "$theustad:doctor",
        "$theustad:run",
        "$theustad:audit",
        "codex plugin remove theustad@personal --json",
        "Linux, macOS, or WSL 2",
        "Native Windows",
        "separate TheUstad-controlled child",
        "## Choose CLI or Codex plugin",
        "Standalone CLI",
        "docs/demo/README.md",
        "docs/PLUGIN_GUIDE.md",
        "GPL-3.0-or-later",
    ):
        assert required in readme


def test_readme_leads_with_verified_problem_and_single_core_architecture():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for required in (
        'Codex says "done." TheUstad checks whether that is true.',
        "https://openai.com/index/how-we-monitor-internal-coding-agents-misalignment/",
        "https://metr.org/evaluations/claude-3-7-report/",
        "https://survey.stackoverflow.co/2025/ai",
        "https://dora.dev/insights/balancing-ai-tensions/",
        "https://arxiv.org/html/2503.15223v1",
        "https://youtu.be/D1nlvLk9iv8",
        "| Without TheUstad | With TheUstad |",
        "same enforcement core",
        "allowlisted copy",
        "TheUstad succeeds when completion becomes falsifiable and reproducible",
        "explicit custom verifier",
        "GPL-3.0-or-later",
    ):
        assert required in readme

    assert "MIT" not in readme


def test_theustad_demo_documents_both_interfaces_and_honesty_boundaries():
    demo = (ROOT / "docs" / "demo" / "README.md").read_text(encoding="utf-8")

    for required in (
        "pytest-dev/iniconfig",
        "77db208ab4ae0cd2061d909fe222a1db72867850",
        "human-authored acceptance test",
        "$theustad:doctor",
        "$theustad:run",
        "$theustad:audit",
        "theustad.py",
        "Linux, macOS, or WSL 2",
        "not an existing upstream issue",
    ):
        assert required in demo


def test_current_release_evidence_records_plugin_video_and_publication():
    evidence = ROOT / "docs" / "evidence" / "theustad-1.0"
    installation = (evidence / "plugin_install.txt").read_text(encoding="utf-8")
    plugin_list = json.loads((evidence / "plugin_list.json").read_text(encoding="utf-8"))
    publication = (evidence / "publication.txt").read_text(encoding="utf-8")
    video_hash = (evidence / "video" / "video_sha256.txt").read_text(encoding="utf-8")

    assert "THEUSTAD_PLUGIN_INSTALLED" in installation
    assert any(
        plugin["pluginId"] == "theustad@personal"
        for plugin in plugin_list["output"]["installed"]
    )
    assert "Visibility: Public" in publication
    assert "https://youtu.be/D1nlvLk9iv8" in publication
    assert "D236FF13EF24A5F1F065F32D1E19158D59AE983C6F0D6C41F993081F62DC1A86" in video_hash
