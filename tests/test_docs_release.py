from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_uses_canonical_release_links_and_commands():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    required = (
        "# TheUstad",
        'Codex says "done." TheUstad checks whether that is true.',
        "https://github.com/YashwanthGathuku/theustad.git",
        "$theustad:doctor",
        "$theustad:run",
        "$theustad:audit",
        "python theustad.py --repo",
        "theustad@personal",
        "THEUSTAD_PYTHON",
        "Linux, macOS, or WSL 2",
        "PASS_NO_CLAIM",
        "custom verifier",
        "AGPL-3.0-or-later",
    )
    for value in required:
        assert value in text


def test_current_docs_use_only_theustad_commands():
    for relative in ("README.md", "docs/PLUGIN_GUIDE.md", "docs/demo/README.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "git clone https://github.com/YashwanthGathuku/theustad" in text or relative != "README.md"
        assert "theustad" in text.lower()


def test_docs_state_honesty_boundaries():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "does not make software 100% correct" in text
    assert "deterministic scripted adversarial rehearsal" in text
    assert "explicit custom verifier" in text
    assert "automatic framework detection" not in text
