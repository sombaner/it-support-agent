"""Printer troubleshooting tool for the IT Support Agent.

Placeholder print-queue lookup that reports printer connectivity and pending
jobs for a user, with safe, ordered troubleshooting steps. Replace
``_PRINT_QUEUES`` with a real print-server source when available.
"""

from __future__ import annotations

_PRINT_QUEUES: dict[str, dict[str, object]] = {
    "alice": {"printer": "HP-3rdFloor", "online": True, "queued_jobs": 0, "error": None},
    "bob": {"printer": "HP-2ndFloor", "online": False, "queued_jobs": 3, "error": "offline"},
}


def _require_user(user: str) -> str:
    if not isinstance(user, str) or not user.strip():
        raise ValueError("user must be a non-empty string")
    return user.strip().lower()


def check_print_queue(user: str) -> dict[str, object]:
    """Return printer status and safe, ordered printer troubleshooting steps.

    Raises ``ValueError`` for a missing user and ``RuntimeError`` when the
    print-queue record is incomplete. Unknown users return an ``unknown_user``
    status rather than raising.
    """

    key = _require_user(user)
    record = _PRINT_QUEUES.get(key)
    if record is None:
        return {"user": key, "status": "unknown_user"}
    try:
        printer = record["printer"]
        online = record["online"]
        queued_jobs = record["queued_jobs"]
        error = record["error"]
    except KeyError as exc:
        raise RuntimeError(f"print queue for {key!r} is incomplete") from exc

    steps = [
        "Confirm the printer is powered on and shows no warning lights or paper jams.",
        "Check the printer's network or USB connection and that it appears online on your device.",
        f"Open the print queue for {printer} and cancel any stuck or errored jobs.",
        "Send a single test page to confirm printing resumes.",
        "Restart the print spooler service (or remove and re-add the printer) if jobs still do not print.",
    ]

    return {
        "user": key,
        "status": "ok",
        "printer": printer,
        "online": online,
        "queued_jobs": queued_jobs,
        "error": error,
        "steps": steps,
        "escalation": (
            "If the printer stays offline or reports a hardware fault, escalate "
            "to Facilities/IT for on-site repair."
        ),
    }
