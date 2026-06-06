"""Drift gate over the committed session fixture.

Policy: models are extra="allow" (parsing never crashes); drift is a CI failure.
These tests assert (a) every event validates, (b) no unmodeled field appears
beyond the documented allowlist, and (c) the gate actually catches a new one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from pi_agent_events import (  # noqa: E402
    AgentEndEvent,
    AutoRetryStartEvent,
    CompactionEndEvent,
    QueueUpdateEvent,
    ToolExecutionEndEvent,
    parse_agent_event,
)
import check_session as cs  # noqa: E402

SESSION = ROOT / "sessions" / "local.jsonl"
ENVELOPES = {"response", "extension_ui_request"}


def _events() -> list[dict]:
    lines = [l for l in SESSION.read_text().splitlines() if l.strip()]
    return [o for o in map(json.loads, lines) if o.get("type") not in ENVELOPES]


def test_every_event_validates() -> None:
    events = _events()
    assert events, "fixture has no agent events"
    for obj in events:
        parse_agent_event(obj)  # extra="allow" -> never raises on a real event


def test_no_unexpected_drift() -> None:
    """The regression gate: no wire field outside expected/known allowlists."""
    drift: set[str] = set()
    for obj in _events():
        evt = parse_agent_event(obj)
        for leaf, full in cs.unmodeled_leaves(evt):
            if cs.classify(leaf, full) == "drift":
                drift.add(leaf)
    assert not drift, f"unexpected unmodeled field(s): {drift} (add to KNOWN_WIRE_EXTRAS or fix pin)"


def test_known_extras_are_actually_exercised() -> None:
    """Guard against a stale allowlist: every KNOWN_WIRE_EXTRA should still show
    up in the fixture, else it can be removed on the next pin bump."""
    seen: set[str] = set()
    for obj in _events():
        evt = parse_agent_event(obj)
        for leaf, _ in cs.unmodeled_leaves(evt):
            if leaf in cs.KNOWN_WIRE_EXTRAS:
                seen.add(leaf)
    assert seen == cs.KNOWN_WIRE_EXTRAS, f"allowlist not fully exercised; only saw {seen}"


def test_injected_unknown_field_is_drift() -> None:
    """The gate must bite: a brand-new wire field is classified as drift."""
    end = next(o for o in _events() if o["type"] == "agent_end")
    end = {**end, "totallyNewField": 123}
    evt = parse_agent_event(end)
    kinds = {cs.classify(leaf, full) for leaf, full in cs.unmodeled_leaves(evt)
             if leaf == "totallyNewField"}
    assert kinds == {"drift"}


def test_typed_payloads_are_usable() -> None:
    by_type = {o["type"]: o for o in _events()}
    end = parse_agent_event(by_type["agent_end"])
    assert isinstance(end, AgentEndEvent) and end.messages
    # willRetry is now a TYPED field (the whole point of switching to
    # AgentSessionEvent), not an allowlisted extra.
    assert isinstance(end.willRetry, bool)
    assert "willRetry" not in (end.model_extra or {})
    tee = parse_agent_event(by_type["tool_execution_end"])
    assert isinstance(tee, ToolExecutionEndEvent) and tee.toolName


def test_session_level_events_parse() -> None:
    """The events that only AgentSessionEvent (not core AgentEvent) defines."""
    q = parse_agent_event({"type": "queue_update", "steering": [], "followUp": ["x"]})
    assert isinstance(q, QueueUpdateEvent) and q.followUp == ["x"]

    ce = parse_agent_event(
        {"type": "compaction_end", "reason": "threshold", "aborted": False,
         "willRetry": True, "result": None}
    )
    assert isinstance(ce, CompactionEndEvent) and ce.willRetry is True

    rs = parse_agent_event(
        {"type": "auto_retry_start", "attempt": 1, "maxAttempts": 3,
         "delayMs": 500, "errorMessage": "boom"}
    )
    assert isinstance(rs, AutoRetryStartEvent) and rs.attempt == 1


def test_non_event_is_rejected() -> None:
    with pytest.raises(Exception):
        parse_agent_event({"type": "response", "command": "prompt", "success": True})
