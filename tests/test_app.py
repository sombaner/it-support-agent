"""Tests for the FastAPI chat surface."""

import asyncio

import pytest
from pydantic import ValidationError

from src.app import ChatRequest, healthz


def test_healthz_reports_ok() -> None:
    assert asyncio.run(healthz()) == {"status": "ok"}


def test_chat_request_normalizes_message() -> None:
    request = ChatRequest(message="  My VPN is down.  ")

    assert request.message == "My VPN is down."


def test_chat_request_rejects_blank_message() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")


def test_chat_request_rejects_oversized_message() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="x" * 4001)