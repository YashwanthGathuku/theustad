import pytest


@pytest.fixture(autouse=True)
def _isolated_claude_config(tmp_path_factory, monkeypatch):
    """No test reads or writes the real Claude Code user settings.

    Enrollment inspects installed hooks and install-hooks writes them; both
    resolve the settings file through CLAUDE_CONFIG_DIR.
    """
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path_factory.mktemp("claude-config")))
