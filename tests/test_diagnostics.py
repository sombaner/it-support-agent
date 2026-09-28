"""Unit tests for the network diagnostics tool."""

import pytest

from src.tools import diagnostics
from src.tools.diagnostics import run_network_diagnostics


def test_run_network_diagnostics_happy_path() -> None:
    result = run_network_diagnostics("alice")

    assert result["status"] == "ok"
    assert result["user"] == "alice"
    assert result["latency_ms"] == 42.0
    assert result["packet_loss_pct"] == 0.4
    assert result["bandwidth_mbps"] == 180.0


def test_run_network_diagnostics_unknown_user() -> None:
    result = run_network_diagnostics("nobody")

    assert result == {"user": "nobody", "status": "unknown_user"}


def test_run_network_diagnostics_missing_user() -> None:
    with pytest.raises(ValueError):
        run_network_diagnostics("   ")


def test_run_network_diagnostics_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(diagnostics._NETWORK_TELEMETRY, "alice", {})

    with pytest.raises(RuntimeError):
        run_network_diagnostics("alice")
