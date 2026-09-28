"""Hosted-agent entry point for Microsoft Foundry (Responses protocol).

Foundry's direct-code deploy runs this module. It reuses ``build_agent()`` from
``src.agent`` (all tools, system prompt, and the ``SupportSummary`` structure on
agent-framework 1.14.0) and serves it over the Responses protocol. Authentication
uses ``DefaultAzureCredential`` (the hosted managed identity); no API keys.
"""

from __future__ import annotations

import asyncio

from agent_framework.foundry import ResponsesHostServer

from src.agent import build_agent


def main() -> None:
    """Serve the IT Support Agent over the Foundry Responses protocol."""

    agent = build_agent()
    asyncio.run(ResponsesHostServer(agent).run_async())


if __name__ == "__main__":
    main()
