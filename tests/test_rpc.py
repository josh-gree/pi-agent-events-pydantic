"""Tests for the prompt command/response halves of the contract.

`test_session.py` covers the async event stream (AgentSessionEvent). Here we
cover driving: constructing a PromptCommand, and parsing the prompt ack — both
the real `response` lines in the captured fixture and a synthetic one.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pi_agent_events import PromptCommand, PromptResponse

SESSION = Path(__file__).resolve().parent.parent / "sessions" / "local.jsonl"


def _lines() -> list[dict]:
    return [json.loads(ln) for ln in SESSION.read_text().splitlines() if ln.strip()]


def test_fixture_prompt_acks_validate() -> None:
    """The real `response` lines in the captured session are prompt acks."""
    responses = [o for o in _lines() if o.get("type") == "response"]
    assert responses, "fixture has no response envelopes"
    for obj in responses:
        ack = PromptResponse.model_validate(obj)
        assert ack.command == "prompt" and ack.success is True


def test_prompt_command_constructs_and_serializes() -> None:
    cmd = PromptCommand(type="prompt", id="1", message="hello")
    dumped = json.loads(cmd.model_dump_json())
    assert dumped["type"] == "prompt"
    assert dumped["message"] == "hello"
    assert dumped["id"] == "1"


def test_prompt_command_roundtrips() -> None:
    obj = {"type": "prompt", "message": "do a thing"}
    cmd = PromptCommand.model_validate(obj)
    assert cmd.message == "do a thing"


def test_contract_surface_has_no_positional_names() -> None:
    """Guard the naming pipeline: no public event/command/response class should
    fall back to a positional name (e.g. `AgentSessionEvent1`)."""
    text = (Path(__file__).resolve().parent.parent
            / "src" / "pi_agent_events" / "models.py").read_text()
    classes = re.findall(r"^class (\w+)\b", text, re.MULTILINE)
    contract = [c for c in classes if c.endswith(("Command", "Event", "Response"))]
    positional = [c for c in contract if re.search(r"\d+$", c)]
    assert not positional, f"positional contract class names: {positional}"
