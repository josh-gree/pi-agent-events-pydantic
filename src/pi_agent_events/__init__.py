"""Pydantic v2 models for the full ``pi --no-extensions --mode rpc`` contract.

Three union roots model the wire, generated from pi's own TypeScript types:

- ``AgentSessionEvent`` — the async event stream pi writes to stdout.
- ``RpcResponse``       — the synchronous reply to each command (also stdout),
                          correlated to its command by ``id``.
- ``RpcCommand``        — the commands you write to stdin to drive the agent.

(The extension-UI request/response types are intentionally omitted: with
``--no-extensions`` they never appear on the wire.)

Reading stdout — validate a line, then read ``.root`` for the concrete model:

    from pi_agent_events import AgentSessionEvent, RpcResponse

    evt  = AgentSessionEvent.model_validate_json(line).root   # e.g. AgentEndEvent
    resp = RpcResponse.model_validate_json(line).root         # e.g. PromptResponse

Driving over stdin — construct a concrete command and serialize it. The concrete
command classes (and every concrete event/response variant, for ``isinstance``
narrowing) live in ``pi_agent_events.models``:

    from pi_agent_events.models import PromptCommand

    proc.stdin.write(PromptCommand(type="prompt", id="1", message="hi").model_dump_json() + "\\n")

``models.py`` is generated — do not edit it by hand; regenerate with ``just gen``.
"""

from __future__ import annotations

from .models import AgentSessionEvent, RpcCommand, RpcResponse

__all__ = ["AgentSessionEvent", "RpcCommand", "RpcResponse"]
