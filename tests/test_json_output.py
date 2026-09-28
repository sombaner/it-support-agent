"""Tests for tolerant JSON extraction from model replies.

Foundry-hosted models do not all enforce ``response_format``, so replies arrive
as bare JSON, fenced JSON, or a fenced block wrapped in conversational prose.
"""

from __future__ import annotations

from src.agent import SupportSummary, extract_json_object, parse_json_model

SUMMARY_JSON = """{
  "issue": "VPN drops during Teams calls",
  "steps_taken": ["Checked VPN status", "Ran network diagnostics"],
  "resolution": "Workaround applied",
  "follow_up": "None"
}"""


def test_bare_json_object():
    assert extract_json_object(SUMMARY_JSON) == SUMMARY_JSON


def test_json_fenced_block():
    text = f"```json\n{SUMMARY_JSON}\n```"
    assert extract_json_object(text) == SUMMARY_JSON


def test_unlabelled_fenced_block():
    text = f"```\n{SUMMARY_JSON}\n```"
    assert extract_json_object(text) == SUMMARY_JSON


def test_prose_preamble_then_fenced_json():
    """The exact shape that broke the CI eval run."""

    text = f"Good news! I've checked your connection.\n\n```json\n{SUMMARY_JSON}\n```"
    parsed = parse_json_model(text, SupportSummary)
    assert parsed is not None
    assert parsed.issue == "VPN drops during Teams calls"


def test_trailing_prose_after_json():
    parsed = parse_json_model(f"{SUMMARY_JSON}\n\nLet me know if that helps!", SupportSummary)
    assert parsed is not None
    assert parsed.resolution == "Workaround applied"


def test_braces_inside_string_values():
    raw = (
        '{"issue": "Config {broken}", "steps_taken": ["Edited {\\"a\\": 1}"], '
        '"resolution": "Fixed", "follow_up": "None"}'
    )
    parsed = parse_json_model(f"Here you go:\n{raw}\nDone.", SupportSummary)
    assert parsed is not None
    assert parsed.issue == "Config {broken}"


def test_no_json_returns_none():
    assert extract_json_object("Sorry, I could not help with that.") is None
    assert parse_json_model("Sorry, I could not help with that.", SupportSummary) is None


def test_wrong_schema_returns_none():
    assert parse_json_model('{"unrelated": true}', SupportSummary) is None
