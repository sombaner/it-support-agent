"""Teams call quality tool for the IT Support Agent.

Placeholder telemetry lookup that reports recent Teams call quality metrics for
a user. Replace ``_TEAMS_CALL_QUALITY`` with a real call analytics source when
available.
"""

from __future__ import annotations

_TEAMS_CALL_QUALITY: dict[str, dict[str, float]] = {
    "alice": {"jitter_ms": 12.0, "packet_loss_pct": 0.5, "round_trip_ms": 60.0},
    "bob": {"jitter_ms": 55.0, "packet_loss_pct": 4.1, "round_trip_ms": 210.0},
}


def _require_user(user: str) -> str:
    if not isinstance(user, str) or not user.strip():
        raise ValueError("user must be a non-empty string")
    return user.strip().lower()


def _rate(jitter_ms: float, packet_loss_pct: float, round_trip_ms: float) -> str:
    if jitter_ms <= 30 and packet_loss_pct <= 1.0 and round_trip_ms <= 100:
        return "good"
    if jitter_ms <= 50 and packet_loss_pct <= 3.0 and round_trip_ms <= 200:
        return "fair"
    return "poor"


def check_teams_call_quality(user: str) -> dict[str, object]:
    """Return recent Teams call quality metrics for a user.

    Raises ``ValueError`` for a missing user and ``RuntimeError`` when the
    telemetry record is incomplete. Unknown users return an ``unknown_user``
    status rather than raising.
    """

    key = _require_user(user)
    record = _TEAMS_CALL_QUALITY.get(key)
    if record is None:
        return {"user": key, "status": "unknown_user"}
    try:
        return {
            "user": key,
            "status": "ok",
            "jitter_ms": record["jitter_ms"],
            "packet_loss_pct": record["packet_loss_pct"],
            "round_trip_ms": record["round_trip_ms"],
            "rating": _rate(
                record["jitter_ms"],
                record["packet_loss_pct"],
                record["round_trip_ms"],
            ),
        }
    except KeyError as exc:
        raise RuntimeError(f"Teams call telemetry for {key!r} is incomplete") from exc
