import pytest


@pytest.fixture(autouse=True)
def _isolated_agent_config(tmp_path_factory, monkeypatch):
    """No test reads or writes the real Claude Code or Codex user settings.

    Enrollment inspects installed hooks and install-hooks writes them; both
    resolve the settings files through CLAUDE_CONFIG_DIR and CODEX_HOME.
    """
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path_factory.mktemp("claude-config")))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path_factory.mktemp("codex-home")))
