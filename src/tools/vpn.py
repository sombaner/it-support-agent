"""VPN status tool for the IT Support Agent.

Placeholder session lookup that reports VPN connection details for a user.
Replace ``_VPN_SESSIONS`` with a real VPN gateway source when available.
"""

from __future__ import annotations

_VPN_SESSIONS: dict[str, dict[str, object]] = {
    "alice": {
        "connected": True,
        "protocol": "IKEv2",
        "server_region": "westus2",
        "throughput_mbps": 45.0,
    },
    "bob": {
        "connected": True,
        "protocol": "OpenVPN",
        "server_region": "eastus",
        "throughput_mbps": 8.0,
    },
}


def _require_user(user: str) -> str:
    if not isinstance(user, str) or not user.strip():
        raise ValueError("user must be a non-empty string")
    return user.strip().lower()


def check_vpn_status(user: str) -> dict[str, object]:
    """Return the current VPN session status for a user.

    Raises ``ValueError`` for a missing user and ``RuntimeError`` when the
    session record is incomplete. Unknown users return an ``unknown_user``
    status rather than raising.
    """

    key = _require_user(user)
    session = _VPN_SESSIONS.get(key)
    if session is None:
        return {"user": key, "status": "unknown_user"}
    try:
        return {
            "user": key,
            "status": "ok",
            "connected": session["connected"],
            "protocol": session["protocol"],
            "server_region": session["server_region"],
            "throughput_mbps": session["throughput_mbps"],
        }
    except KeyError as exc:
        raise RuntimeError(f"VPN session for {key!r} is incomplete") from exc
