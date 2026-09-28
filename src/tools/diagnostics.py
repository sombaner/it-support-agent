"""Network diagnostics tool for the IT Support Agent.

Placeholder telemetry lookup that reports basic network health for a user.
Replace ``_NETWORK_TELEMETRY`` with a real telemetry source when available.
"""

from __future__ import annotations

_NETWORK_TELEMETRY: dict[str, dict[str, float]] = {
    "alice": {"latency_ms": 42.0, "packet_loss_pct": 0.4, "bandwidth_mbps": 180.0},
    "bob": {"latency_ms": 130.0, "packet_loss_pct": 3.2, "bandwidth_mbps": 22.5},
}


def _require_user(user: str) -> str:
    if not isinstance(user, str) or not user.strip():
        raise ValueError("user must be a non-empty string")
    return user.strip().lower()


def run_network_diagnostics(user: str) -> dict[str, object]:
    """Return basic network diagnostics for a user.

    Raises ``ValueError`` for a missing user and ``RuntimeError`` when the
    telemetry record is incomplete. Unknown users return an ``unknown_user``
    status rather than raising.
    """

    key = _require_user(user)
    record = _NETWORK_TELEMETRY.get(key)
    if record is None:
        return {"user": key, "status": "unknown_user"}
    try:
        return {
            "user": key,
            "status": "ok",
            "latency_ms": record["latency_ms"],
            "packet_loss_pct": record["packet_loss_pct"],
            "bandwidth_mbps": record["bandwidth_mbps"],
        }
    except KeyError as exc:
        raise RuntimeError(f"network telemetry for {key!r} is incomplete") from exc
