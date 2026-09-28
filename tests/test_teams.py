"""Unit tests for the Teams call quality tool."""

import pytest

from src.tools import teams
from src.tools.teams import check_teams_call_quality


def test_check_teams_call_quality_happy_path() -> None:
    result = check_teams_call_quality("alice")

    assert result["status"] == "ok"
    assert result["user"] == "alice"
    assert result["jitter_ms"] == 12.0
    assert result["packet_loss_pct"] == 0.5
    assert result["round_trip_ms"] == 60.0
    assert result["rating"] == "good"


def test_check_teams_call_quality_poor_rating() -> None:
    result = check_teams_call_quality("bob")

    assert result["status"] == "ok"
    assert result["rating"] == "poor"


def test_check_teams_call_quality_unknown_user() -> None:
    result = check_teams_call_quality("nobody")

    assert result == {"user": "nobody", "status": "unknown_user"}


def test_check_teams_call_quality_missing_user() -> None:
    with pytest.raises(ValueError):
        check_teams_call_quality(None)  # type: ignore[arg-type]


def test_check_teams_call_quality_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(teams._TEAMS_CALL_QUALITY, "alice", {"jitter_ms": 12.0})

    with pytest.raises(RuntimeError):
        check_teams_call_quality("alice")
