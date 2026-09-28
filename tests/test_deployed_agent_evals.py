"""Tests for invoking the deployed Foundry agent through azd."""

from __future__ import annotations

import asyncio

import pytest

from evals import run_deployed_agent_evals as deployed_evals


class FakeProcess:
    def __init__(self, stdout: bytes, stderr: bytes, returncode: int) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.stdout, self.stderr


def test_invoke_names_agent_in_fresh_azd_environment(monkeypatch):
    captured_args: tuple[str, ...] = ()

    async def create_process(*args, **kwargs):
        nonlocal captured_args
        captured_args = args
        return FakeProcess(b'{"resolution": "Connected"}', b"", 0)

    monkeypatch.setattr(deployed_evals.asyncio, "create_subprocess_exec", create_process)

    answer = asyncio.run(
        deployed_evals.invoke_deployed_agent({"ticket": "Check VPN", "id": "vpn"})
    )

    assert captured_args[:5] == (
        deployed_evals.AZD_BIN,
        "ai",
        "agent",
        "invoke",
        deployed_evals.AGENT_NAME,
    )
    assert answer == '{"resolution": "Connected"}'


def test_invoke_failure_includes_stdout_diagnostics(monkeypatch):
    async def create_process(*args, **kwargs):
        return FakeProcess(b"ERROR: agent was not found\n", b"", 1)

    monkeypatch.setattr(deployed_evals.asyncio, "create_subprocess_exec", create_process)

    with pytest.raises(RuntimeError, match="agent was not found"):
        asyncio.run(
            deployed_evals.invoke_deployed_agent(
                {"ticket": "Check VPN", "id": "vpn"}
            )
        )