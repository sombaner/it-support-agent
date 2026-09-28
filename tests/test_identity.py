"""Unit tests for the account/password-reset tool."""

import pytest

from src.tools import identity
from src.tools.identity import SSPR_PORTAL, check_account_status


def test_check_account_status_happy_path() -> None:
    result = check_account_status("alice")

    assert result["status"] == "ok"
    assert result["user"] == "alice"
    assert result["locked"] is True
    assert result["lockout_minutes"] == 30
    assert result["self_service_portal"] == SSPR_PORTAL
    assert isinstance(result["steps"], list)
    assert result["steps"]
    assert all(isinstance(step, str) and step.strip() for step in result["steps"])
    # The tool must never request or return a password.
    assert not any("password" in step.lower() and "share" in step.lower() for step in result["steps"])


def test_check_account_status_unknown_user() -> None:
    result = check_account_status("nobody")

    assert result == {"user": "nobody", "status": "unknown_user"}


def test_check_account_status_missing_user() -> None:
    with pytest.raises(ValueError):
        check_account_status("")


def test_check_account_status_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(identity._ACCOUNTS, "alice", {"locked": True})

    with pytest.raises(RuntimeError):
        check_account_status("alice")
