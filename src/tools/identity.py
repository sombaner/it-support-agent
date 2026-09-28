"""Account and password-reset tool for the IT Support Agent.

Placeholder identity lookup that reports account lockout state and self-service
password-reset guidance for a user. Replace ``_ACCOUNTS`` with a real identity
provider (for example, Microsoft Entra ID) when available. This tool never
handles, requests, or returns passwords or secrets.
"""

from __future__ import annotations

SSPR_PORTAL = "https://aka.ms/sspr"

_ACCOUNTS: dict[str, dict[str, object]] = {
    "alice": {"locked": True, "lockout_minutes": 30, "mfa_enrolled": True},
    "bob": {"locked": False, "lockout_minutes": 30, "mfa_enrolled": False},
}


def _require_user(user: str) -> str:
    if not isinstance(user, str) or not user.strip():
        raise ValueError("user must be a non-empty string")
    return user.strip().lower()


def check_account_status(user: str) -> dict[str, object]:
    """Return account lockout state and self-service password-reset guidance.

    Never requests or returns passwords. Raises ``ValueError`` for a missing
    user and ``RuntimeError`` when the account record is incomplete. Unknown
    users return an ``unknown_user`` status rather than raising.
    """

    key = _require_user(user)
    account = _ACCOUNTS.get(key)
    if account is None:
        return {"user": key, "status": "unknown_user"}
    try:
        locked = account["locked"]
        lockout_minutes = account["lockout_minutes"]
        mfa_enrolled = account["mfa_enrolled"]
    except KeyError as exc:
        raise RuntimeError(f"account record for {key!r} is incomplete") from exc

    steps = [
        f"Open the self-service password reset portal at {SSPR_PORTAL}.",
        "Enter your work email or user ID and start the reset flow.",
        "Verify your identity with your registered MFA method (authenticator app, SMS, or phone call).",
        "Choose a new password that meets the corporate complexity policy.",
        "Sign in with the new password; a locked account unlocks automatically once the lockout window elapses.",
    ]
    if not mfa_enrolled:
        steps.append(
            "You are not enrolled in MFA, which self-service reset requires — "
            "contact the IT service desk to reset your password and enroll in MFA."
        )

    return {
        "user": key,
        "status": "ok",
        "locked": locked,
        "lockout_minutes": lockout_minutes,
        "mfa_enrolled": mfa_enrolled,
        "self_service_portal": SSPR_PORTAL,
        "steps": steps,
        "escalation": (
            "If self-service reset fails or MFA is unavailable, contact the IT "
            "service desk to unlock the account."
        ),
        "note": "Never share your current or new password with anyone, including IT support.",
    }
