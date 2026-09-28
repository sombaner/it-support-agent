"""Endpoint health tool for the IT Support Agent.

Placeholder device-telemetry lookup that reports performance and stability
signals for a user's laptop (CPU, memory, disk, startup load, pending reboot,
and the last recorded crash stop code), with safe, ordered triage steps.
Replace ``_ENDPOINT_HEALTH`` with a real device-management source (for example,
Intune) when available.
"""

from __future__ import annotations

_ENDPOINT_HEALTH: dict[str, dict[str, object]] = {
    "alice": {
        "cpu_pct": 88.0,
        "memory_pct": 91.0,
        "disk_free_gb": 6.5,
        "startup_apps": 24,
        "pending_reboot": True,
        "last_stop_code": None,
    },
    "bob": {
        "cpu_pct": 35.0,
        "memory_pct": 60.0,
        "disk_free_gb": 120.0,
        "startup_apps": 8,
        "pending_reboot": False,
        "last_stop_code": "IRQL_NOT_LESS_OR_EQUAL",
    },
}


def _require_user(user: str) -> str:
    if not isinstance(user, str) or not user.strip():
        raise ValueError("user must be a non-empty string")
    return user.strip().lower()


def check_endpoint_health(user: str) -> dict[str, object]:
    """Return endpoint performance/stability signals and safe triage steps.

    Covers slow-performance and crash (blue screen) symptoms. Raises
    ``ValueError`` for a missing user and ``RuntimeError`` when the telemetry
    record is incomplete. Unknown users return an ``unknown_user`` status
    rather than raising.
    """

    key = _require_user(user)
    record = _ENDPOINT_HEALTH.get(key)
    if record is None:
        return {"user": key, "status": "unknown_user"}
    try:
        cpu_pct = record["cpu_pct"]
        memory_pct = record["memory_pct"]
        disk_free_gb = record["disk_free_gb"]
        startup_apps = record["startup_apps"]
        pending_reboot = record["pending_reboot"]
        last_stop_code = record["last_stop_code"]
    except KeyError as exc:
        raise RuntimeError(f"endpoint telemetry for {key!r} is incomplete") from exc

    steps = [
        "Open Task Manager and review CPU, memory, and disk usage to spot heavy processes.",
        "Close or restart any application consuming excessive resources.",
        "Free disk space if the system drive is low (empty the Recycle Bin and clear temp files).",
        "Disable unnecessary startup apps so fewer programs launch at sign-in.",
        "Install pending Windows and driver updates, then restart the device.",
    ]
    if isinstance(disk_free_gb, (int, float)) and disk_free_gb < 10:
        steps.append(
            "Free disk space (only "
            f"{disk_free_gb} GB free): empty the Recycle Bin, delete temporary files, "
            "and move large files to OneDrive."
        )
    if last_stop_code:
        steps.append(
            f"Note the blue-screen stop code ({last_stop_code}) and update or roll back the "
            "related device driver."
        )

    return {
        "user": key,
        "status": "ok",
        "cpu_pct": cpu_pct,
        "memory_pct": memory_pct,
        "disk_free_gb": disk_free_gb,
        "startup_apps": startup_apps,
        "pending_reboot": pending_reboot,
        "last_stop_code": last_stop_code,
        "steps": steps,
        "escalation": (
            "If the device stays slow or keeps crashing after these steps, escalate to "
            "IT for hardware diagnostics or a driver/OS repair."
        ),
    }
