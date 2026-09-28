"""Evaluation harness for the *deployed* IT Support Agent.

Mirrors ``run_evals.py`` but sources each answer from the live Foundry hosted
agent via ``azd ai agent invoke`` instead of building the agent in-process. The
judge, the ticket set, and the scored dimensions are shared with ``run_evals``
so scores are directly comparable between the two harnesses.

Requires an azd environment configured for the target Foundry project (see the
``evaluate-deployed-agent`` job in ``.github/workflows/deploy-to-foundry.yml``)
and, for the judge, ``FOUNDRY_PROJECT_ENDPOINT`` / ``FOUNDRY_MODEL_DEPLOYMENT``.

Environment variables:
    AZD_BIN               Path to the azd binary (default ``azd``).
    AZD_AGENT_NAME        Deployed agent name (default ``it-support-agent``).
    EVAL_INVOKE_TIMEOUT   Per-ticket invoke timeout in seconds (default 180).
    EVAL_THRESHOLD        Minimum per-score threshold (default 3.0).
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

from evals.run_evals import (
    build_judge,
    build_message,
    evaluate_cases,
    load_cases,
    report,
    require_settings,
)
from src.agent import SupportSummary, parse_json_model

REPO_ROOT = Path(__file__).resolve().parent.parent
AZD_BIN = os.environ.get("AZD_BIN", "azd")
AGENT_NAME = os.environ.get("AZD_AGENT_NAME", "it-support-agent")
INVOKE_TIMEOUT = float(os.environ.get("EVAL_INVOKE_TIMEOUT", "180"))

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_GLYPH_LINE = re.compile(r"^\([^)]{1,3}\)\s")
_CHROME_PREFIXES = ("SUCCESS:", "WARNING:", "ERROR:", "INFO:", "Invoking")


def clean_azd_output(output: str) -> str:
    """Strip azd's ANSI colours and progress chrome, leaving the agent's reply."""

    kept = []
    for line in _ANSI.sub("", output).splitlines():
        stripped = line.strip()
        if _GLYPH_LINE.match(stripped) or stripped.startswith(_CHROME_PREFIXES):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


async def invoke_deployed_agent(case: dict) -> str:
    """Send one ticket to the deployed agent and return its answer as text."""

    process = await asyncio.create_subprocess_exec(
        AZD_BIN,
        "ai",
        "agent",
        "invoke",
        AGENT_NAME,
        build_message(case),
        cwd=REPO_ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=INVOKE_TIMEOUT
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError(
            f"`azd ai agent invoke` timed out after {INVOKE_TIMEOUT:.0f}s"
        ) from None

    if process.returncode != 0:
        detail = "\n".join(
            part
            for part in (
                _ANSI.sub("", stdout.decode(errors="replace")).strip(),
                _ANSI.sub("", stderr.decode(errors="replace")).strip(),
            )
            if part
        ) or "(no output)"
        raise RuntimeError(
            f"`azd ai agent invoke` exited {process.returncode}: {detail}"
        )

    answer = clean_azd_output(stdout.decode(errors="replace"))
    if not answer:
        raise RuntimeError("`azd ai agent invoke` returned no output")

    # The deployed agent sets no response_format at all, so tolerant parsing is
    # mandatory here rather than a fallback.
    summary = parse_json_model(answer, SupportSummary)
    return summary.model_dump_json(indent=2) if summary is not None else answer


async def main() -> None:
    require_settings()
    threshold = float(os.environ.get("EVAL_THRESHOLD", "3.0"))
    print(
        f"Evaluating the deployed agent via "
        f"`{AZD_BIN} ai agent invoke {AGENT_NAME}`.\n"
    )
    rows, failures, errors = await evaluate_cases(
        load_cases(), invoke_deployed_agent, build_judge(), threshold
    )
    sys.exit(report(rows, failures, errors, threshold))


if __name__ == "__main__":
    asyncio.run(main())
