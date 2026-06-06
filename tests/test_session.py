"""Parse the committed `pi --mode rpc` transcript through the generated models.

`sessions/local.jsonl` is a real captured session. Every line that is not an RPC
envelope (`response` / `extension_ui_request`) is an `AgentSessionEvent` and must
validate against the generated models — this is the regression gate for both the
generation pipeline and the pinned pi version.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from pi_agent_events import AgentSessionEvent

SESSION = Path(__file__).resolve().parent.parent / "sessions" / "local.jsonl"
ENVELOPES = {"response", "extension_ui_request"}


def _events() -> list[dict]:
    lines = [ln for ln in SESSION.read_text().splitlines() if ln.strip()]
    return [o for o in map(json.loads, lines) if o.get("type") not in ENVELOPES]


def test_fixture_present() -> None:
    assert SESSION.exists(), f"missing transcript fixture: {SESSION}"
    assert _events(), "fixture has no agent events"


def test_every_event_parses() -> None:
    failures: list[tuple[int, str | None, str]] = []
    for n, obj in enumerate(_events(), 1):
        try:
            AgentSessionEvent.model_validate(obj)
        except ValidationError as e:
            failures.append((n, obj.get("type"), str(e.errors(include_url=False)[0])[:200]))
    assert not failures, (
        f"{len(failures)} event(s) failed to parse; first few: {failures[:3]}"
    )
