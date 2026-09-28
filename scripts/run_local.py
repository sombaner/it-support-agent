"""Run the IT Support Agent locally against a sample VPN/Teams question."""

from __future__ import annotations

import asyncio

from src.agent import run

QUESTION = "My Teams meeting quality is poor when connected to VPN."


async def main() -> None:
    summary = await run(QUESTION)
    print(f"Question: {QUESTION}\n")
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
