"""Smoke tests for the scaffolded IT Support Agent."""

from src.agent import AgentSettings, load_settings


def test_load_settings_returns_agent_settings() -> None:
    """Verify the settings loader returns the expected settings object."""

    settings = load_settings()

    assert isinstance(settings, AgentSettings)
