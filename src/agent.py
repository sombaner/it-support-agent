"""IT Support Agent built on the Microsoft Agent Framework.

Loads the system prompt, registers six support tools, and runs a model
deployment hosted in a Microsoft Foundry project. Authentication uses
``DefaultAzureCredential`` (for example, an ``az login`` session); no API keys
are read from code or environment. The agent returns a structured support
summary: issue, steps taken, resolution, and follow-up.

Required environment variables (set in ``.env``):
    FOUNDRY_PROJECT_ENDPOINT  Microsoft Foundry project endpoint.
    FOUNDRY_MODEL_DEPLOYMENT  Model deployment name.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar
from urllib.parse import urlsplit

from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from src.tools.diagnostics import run_network_diagnostics
from src.tools.endpoint import check_endpoint_health
from src.tools.identity import check_account_status
from src.tools.printing import check_print_queue
from src.tools.teams import check_teams_call_quality
from src.tools.vpn import check_vpn_status

PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"
AGENT_NAME = "it-support-agent"

TModel = TypeVar("TModel", bound=BaseModel)

_FENCED_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class SupportSummary(BaseModel):
    """Structured resolution summary returned by the IT Support Agent."""

    issue: str = Field(description="One-line description of the reported problem.")
    steps_taken: list[str] = Field(
        description="Ordered troubleshooting steps that were performed."
    )
    resolution: str = Field(
        description="Outcome: resolved, workaround applied, or escalated."
    )
    follow_up: str = Field(
        description="Recommended next steps, or 'None' if no follow-up is needed."
    )


def _first_balanced_object(text: str) -> str | None:
    """Return the first brace-balanced ``{...}`` span, ignoring braces inside strings."""

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def extract_json_object(text: str) -> str | None:
    """Return the first JSON object in ``text``, unwrapping any markdown fence.

    Not every model served through Foundry's OpenAI-compatible surface honours
    ``response_format``, so replies routinely arrive as prose wrapped around a
    fenced JSON block rather than as a bare object.
    """

    for match in _FENCED_BLOCK.finditer(text):
        candidate = _first_balanced_object(match.group(1))
        if candidate is not None:
            return candidate
    return _first_balanced_object(text)


def parse_json_model(text: str, model_cls: type[TModel]) -> TModel | None:
    """Validate the JSON object embedded in ``text`` against ``model_cls``."""

    candidate = extract_json_object(text)
    if candidate is None:
        return None
    try:
        return model_cls.model_validate_json(candidate)
    except ValidationError:
        return None


@dataclass(frozen=True)
class AgentSettings:
    """Runtime configuration read from environment variables."""

    project_endpoint: str
    model_deployment_name: str


def load_settings() -> AgentSettings:
    """Load Foundry connection settings from the environment.

    Reads the local ``FOUNDRY_*`` variables first, then the ``AZURE_AI_*`` names
    that the hosted Foundry runtime and azd inject, so the same code runs locally
    and when deployed as a hosted agent.
    """

    load_dotenv()
    endpoint = (
        os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        or os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
        or ""
    )
    model = (
        os.environ.get("FOUNDRY_MODEL_DEPLOYMENT")
        or os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        or ""
    )
    return AgentSettings(project_endpoint=endpoint, model_deployment_name=model)


def load_system_prompt() -> str:
    """Read the IT Support Agent system instructions from disk."""

    return PROMPT_PATH.read_text(encoding="utf-8")


def _base_url(endpoint: str) -> str:
    """Derive the Azure OpenAI v1 base URL from any Foundry endpoint shape.

    Accepts the openai/v1 form (``.../openai/v1[/responses]``) or a Foundry
    project endpoint (``.../api/projects/<name>``) and returns
    ``https://<host>/openai/v1/``.
    """

    parts = urlsplit(endpoint)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}/openai/v1/"
    raw = endpoint.rstrip("/")
    if raw.endswith("/responses"):
        raw = raw[: -len("/responses")]
    return raw + "/"


async def run(query: str) -> SupportSummary:
    """Run the IT Support Agent against a single user query."""

    agent = build_agent()
    result = await agent.run(query)
    summary = parse_json_model(result.text, SupportSummary)
    if summary is None:
        raise ValueError(
            f"Agent did not return a parseable support summary:\n{result.text}"
        )
    return summary


def build_agent():
    """Create the IT Support Agent with its tools and system prompt."""

    settings = load_settings()
    if not settings.project_endpoint or not settings.model_deployment_name:
        raise RuntimeError(
            "Set FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_DEPLOYMENT in .env "
            "and sign in with `az login` before running."
        )

    # Deferred import: keeps module import (and tests) independent of the chat client build.
    from agent_framework import Agent
    from agent_framework.openai import OpenAIChatClient

    # OpenAIChatClient routes to Azure when a credential is supplied; base_url is the
    # full Azure OpenAI v1 surface (".../openai/v1/") derived from the Foundry endpoint.
    client = OpenAIChatClient(
        base_url=_base_url(settings.project_endpoint),
        model=settings.model_deployment_name,
        credential=DefaultAzureCredential(),
    )
    return Agent(
        client,
        name=AGENT_NAME,
        instructions=load_system_prompt(),
        tools=[
            run_network_diagnostics,
            check_vpn_status,
            check_teams_call_quality,
            check_account_status,
            check_print_queue,
            check_endpoint_health,
        ],
    )


async def main() -> None:
    """Run a sample IT support request and print the structured summary."""

    query = (
        "The signed-in user_id is 'alice'. Use it for any tool calls that need a user.\n\n"
        "I'm working from home and my VPN keeps dropping, and now my Microsoft Teams "
        "calls are choppy with bad audio. Can you help me figure out what's wrong?"
    )
    summary = await run(query)
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
