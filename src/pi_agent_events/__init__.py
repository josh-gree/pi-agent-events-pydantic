"""Pydantic v2 models for the event stream ``pi --mode rpc`` writes to stdout.

The single public type is ``AgentSessionEvent`` — a ``RootModel`` union of every
concrete event pi emits. Validate a stdout line (that is not an RPC envelope)
with it; ``.root`` is the concrete event:

    from pi_agent_events import AgentSessionEvent

    evt = AgentSessionEvent.model_validate_json(line).root
    # evt is e.g. an AgentEndEvent / ToolExecutionStartEvent / ...

The concrete variant classes (for ``isinstance`` narrowing or type annotations)
live in ``pi_agent_events.models``; they are reachable through the union here.
``models.py`` is generated — do not edit it by hand; regenerate with ``just gen``.
"""

from __future__ import annotations

from .models import AgentSessionEvent

__all__ = ["AgentSessionEvent"]
