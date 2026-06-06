"""Pydantic v2 models for the slice of `pi --no-extensions --mode rpc` we use.

Three roots, generated from pi's own TypeScript types:

- ``AgentSessionEvent`` — the async event stream pi writes to stdout.
- ``PromptResponse``    — the synchronous ack for a prompt command (also stdout),
                          correlated to the command by ``id``.
- ``PromptCommand``     — the command we write to stdin to drive the agent.

(Only the prompt command/response are modeled; pi's other ~28 commands, its
generic command responses, and the whole model/provider descriptor are out of
scope — add them later if needed.)

Reading stdout — validate a line, then read ``.root`` for the concrete event:

    from pi_agent_events import AgentSessionEvent, PromptResponse

    evt = AgentSessionEvent.model_validate_json(line).root   # e.g. AgentEndEvent
    ack = PromptResponse.model_validate_json(line)           # command="prompt", success=True

Driving over stdin — construct a prompt and serialize it:

    from pi_agent_events import PromptCommand

    proc.stdin.write(PromptCommand(type="prompt", id="1", message="hi").model_dump_json() + "\\n")

``AgentSessionEvent`` is a ``RootModel`` union; its concrete event variants (for
``isinstance`` / annotations) live in ``pi_agent_events.models``. ``models.py`` is
generated — do not edit it by hand; regenerate with ``just gen``.
"""

from __future__ import annotations

from .models import AgentSessionEvent, PromptCommand, PromptResponse

__all__ = ["AgentSessionEvent", "PromptCommand", "PromptResponse"]
