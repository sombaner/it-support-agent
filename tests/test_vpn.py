"""Unit tests for the VPN status tool."""

import pytest

from src.tools import vpn
from src.tools.vpn import check_vpn_status


def test_check_vpn_status_happy_path() -> None:
    result = check_vpn_status("bob")

    assert result["status"] == "ok"
    assert result["user"] == "bob"
    assert result["connected"] is True
    assert result["protocol"] == "OpenVPN"
    assert result["server_region"] == "eastus"
    assert result["throughput_mbps"] == 8.0


def test_check_vpn_status_unknown_user() -> None:
    result = check_vpn_status("nobody")

    assert result == {"user": "nobody", "status": "unknown_user"}


def test_check_vpn_status_missing_user() -> None:
    with pytest.raises(ValueError):
        check_vpn_status("")


def test_check_vpn_status_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(vpn._VPN_SESSIONS, "bob", {"connected": True})

    with pytest.raises(RuntimeError):
        check_vpn_status("bob")
