"""Tests for the command/response halves of the `--mode rpc` contract.

`test_session.py` covers the async event stream (AgentSessionEvent). Here we
cover the synchronous reply envelopes (RpcResponse) — including the real ones in
the captured fixture — and constructing/parsing the commands you drive pi with
(RpcCommand).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pi_agent_events import RpcCommand, RpcResponse
from pi_agent_events.models import AbortCommand, BashCommand, PromptCommand

SESSION = Path(__file__).resolve().parent.parent / "sessions" / "local.jsonl"


def _lines() -> list[dict]:
    return [json.loads(ln) for ln in SESSION.read_text().splitlines() if ln.strip()]


def test_fixture_response_envelopes_validate() -> None:
    """The real `response` lines in the captured session parse as RpcResponse."""
    responses = [o for o in _lines() if o.get("type") == "response"]
    assert responses, "fixture has no response envelopes"
    for obj in responses:
        r = RpcResponse.model_validate(obj).root
        assert r.command and r.success is True


def test_prompt_command_roundtrips_through_union() -> None:
    cmd = PromptCommand(type="prompt", id="1", message="hello")
    dumped = json.loads(cmd.model_dump_json())
    assert dumped["type"] == "prompt" and dumped["message"] == "hello"
    back = RpcCommand.model_validate(dumped).root
    assert isinstance(back, PromptCommand) and back.message == "hello"


def test_commands_resolve_to_their_concrete_class() -> None:
    cases = [
        ({"type": "abort"}, AbortCommand),
        ({"type": "bash", "command": "ls"}, BashCommand),
        ({"type": "prompt", "message": "x"}, PromptCommand),
    ]
    for obj, cls in cases:
        assert isinstance(RpcCommand.model_validate(obj).root, cls)


def test_error_response_parses() -> None:
    err = {"type": "response", "command": "prompt", "success": False, "error": "boom"}
    r = RpcResponse.model_validate(err).root
    assert r.success is False and r.error == "boom"


def test_contract_surface_has_no_positional_names() -> None:
    """Guard the naming pipeline: no public event/command/response/result class
    should fall back to a positional name (e.g. `RpcCommand1`). Deep pi-ai detail
    types are out of scope here."""
    text = (Path(__file__).resolve().parent.parent
            / "src" / "pi_agent_events" / "models.py").read_text()
    classes = re.findall(r"^class (\w+)\b", text, re.MULTILINE)
    contract = [c for c in classes if c.endswith(("Command", "Event", "Response", "Result"))]
    positional = [c for c in contract if re.search(r"\d+$", c)]
    assert not positional, f"positional contract class names: {positional}"
