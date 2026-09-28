"""Unit tests for the structured support summary schema and prompt."""

from evals.run_evals import JUDGE_INSTRUCTIONS
from src.agent import SupportSummary, load_system_prompt


def test_support_summary_has_expected_fields() -> None:
    summary = SupportSummary(
        issue="Poor Teams call quality on VPN.",
        steps_taken=["Checked VPN status.", "Reviewed Teams call metrics."],
        resolution="Enabled split tunneling for Teams media.",
        follow_up="Monitor call quality for 24 hours.",
    )

    dumped = summary.model_dump()

    assert set(dumped) == {"issue", "steps_taken", "resolution", "follow_up"}
    assert summary.issue
    assert isinstance(summary.steps_taken, list) and summary.steps_taken
    assert summary.resolution
    assert summary.follow_up


def test_system_prompt_requires_support_summary_json() -> None:
    prompt = load_system_prompt()

    assert "Return only a valid JSON object" in prompt
    for field in ("issue", "steps_taken", "resolution", "follow_up"):
        assert f"`{field}`" in prompt
    assert 'the string `"None"`' in prompt


def test_judge_instructions_require_score_json() -> None:
    assert "Return only a valid JSON object" in JUDGE_INSTRUCTIONS
    assert "integers from 1 to 5" in JUDGE_INSTRUCTIONS
    for field in ("correctness", "groundedness", "safety", "relevance", "rationale"):
        assert field in JUDGE_INSTRUCTIONS
