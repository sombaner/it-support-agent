"""Unit tests for the endpoint health tool."""

import pytest

from src.tools import endpoint
from src.tools.endpoint import check_endpoint_health


def test_check_endpoint_health_happy_path() -> None:
    result = check_endpoint_health("alice")

    assert result["status"] == "ok"
    assert result["user"] == "alice"
    assert result["cpu_pct"] == 88.0
    assert result["pending_reboot"] is True
    assert isinstance(result["steps"], list)
    assert result["steps"]
    assert all(isinstance(step, str) and step.strip() for step in result["steps"])
    assert result["escalation"]


def test_check_endpoint_health_includes_low_disk_step_for_alice() -> None:
    result = check_endpoint_health("alice")

    assert result["disk_free_gb"] < 10
    assert any(
        "OneDrive" in step and "Recycle Bin" in step for step in result["steps"]
    )


def test_check_endpoint_health_includes_crash_step_when_stop_code_present() -> None:
    result = check_endpoint_health("bob")

    assert result["last_stop_code"] == "IRQL_NOT_LESS_OR_EQUAL"
    assert any("IRQL_NOT_LESS_OR_EQUAL" in step for step in result["steps"])


def test_check_endpoint_health_unknown_user() -> None:
    result = check_endpoint_health("nobody")

    assert result == {"user": "nobody", "status": "unknown_user"}


def test_check_endpoint_health_missing_user() -> None:
    with pytest.raises(ValueError):
        check_endpoint_health("")


def test_check_endpoint_health_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(endpoint._ENDPOINT_HEALTH, "alice", {"cpu_pct": 88.0})

    with pytest.raises(RuntimeError):
        check_endpoint_health("alice")
