"""Unit tests for the printer troubleshooting tool."""

import pytest

from src.tools import printing
from src.tools.printing import check_print_queue


def test_check_print_queue_happy_path() -> None:
    result = check_print_queue("bob")

    assert result["status"] == "ok"
    assert result["user"] == "bob"
    assert result["printer"] == "HP-2ndFloor"
    assert result["online"] is False
    assert result["queued_jobs"] == 3
    assert isinstance(result["steps"], list)
    assert result["steps"]
    assert all(isinstance(step, str) and step.strip() for step in result["steps"])
    assert result["escalation"]


def test_check_print_queue_unknown_user() -> None:
    result = check_print_queue("nobody")

    assert result == {"user": "nobody", "status": "unknown_user"}


def test_check_print_queue_missing_user() -> None:
    with pytest.raises(ValueError):
        check_print_queue("   ")


def test_check_print_queue_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(printing._PRINT_QUEUES, "bob", {"printer": "HP-2ndFloor"})

    with pytest.raises(RuntimeError):
        check_print_queue("bob")
