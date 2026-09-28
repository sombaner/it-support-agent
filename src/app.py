"""Minimal FastAPI demo surface for the IT Support Agent.

Exposes ``POST /chat`` which streams the agent's response as plain text, and
serves the single-page chat box at ``/``. For live demo use only.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from src.agent import build_agent

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
DEMO_USER_ID = os.environ.get("DEMO_USER_ID", "alice")

app = FastAPI(title="IT Support Agent Demo")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    user_id: str | None = None

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        """Normalize chat input and reject whitespace-only messages."""

        message = value.strip()
        if not message:
            raise ValueError("message must not be blank")
        return message


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness/readiness probe target for Container Apps."""

    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    agent = build_agent()
    user_id = request.user_id or DEMO_USER_ID
    message = (
        f"The signed-in user_id is '{user_id}'. "
        f"Use it for any tool calls that need a user.\n\n{request.message}"
    )

    async def stream():
        async for update in agent.run(message, stream=True):
            if update.text:
                yield update.text

    return StreamingResponse(stream(), media_type="text/plain")

