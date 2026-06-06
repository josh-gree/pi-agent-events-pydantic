"""Pydantic v2 models for what ``pi --mode rpc`` emits on stdout.

The wire type is pi-coding-agent's ``AgentSessionEvent`` (NOT pi-agent-core's
``AgentEvent``): a superset that adds ``willRetry`` to ``agent_end`` and adds the
session-level events (queue_update, compaction_start/end, auto_retry_start/end,
session_info_changed, thinking_level_changed). Generated from a pinned pi version
(see ``pi_version.txt``); do not edit ``models.py`` by hand — run
``scripts/generate.sh`` and commit.

Policy is extra="allow" at runtime + a CI drift gate (scripts/check_session.py);
see the README. Each stdout line that is not an RPC envelope
(``response`` / ``extension_ui_request``) is an event:

    from pi_agent_events import parse_agent_event, AgentEndEvent
    evt = parse_agent_event(line)
    if isinstance(evt, AgentEndEvent):
        if evt.willRetry: ...
        for m in evt.messages: ...
"""

from __future__ import annotations

import json

from .models import (
    AgentEndEvent,
    AgentSessionEvent,  # RootModel union of every concrete event below
    AgentStartEvent,
    AutoRetryEndEvent,
    AutoRetryStartEvent,
    CompactionEndEvent,
    CompactionStartEvent,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    QueueUpdateEvent,
    SessionInfoChangedEvent,
    ThinkingLevelChangedEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    TurnEndEvent,
    TurnStartEvent,
)


def parse_agent_event(line_or_obj: str | bytes | dict):
    """Validate one session event into its concrete model.

    Accepts a JSONL line (``str``/``bytes``) or a parsed ``dict``; returns the
    concrete event (e.g. ``AgentEndEvent``). Raises ``pydantic.ValidationError``
    if it is not a known event — which is how an RPC ``response`` /
    ``extension_ui_request`` that slipped through here gets rejected.
    """
    obj = json.loads(line_or_obj) if isinstance(line_or_obj, (str, bytes)) else line_or_obj
    return AgentSessionEvent.model_validate(obj).root


__all__ = [
    "AgentSessionEvent",
    "parse_agent_event",
    # core agent events
    "AgentStartEvent",
    "AgentEndEvent",
    "TurnStartEvent",
    "TurnEndEvent",
    "MessageStartEvent",
    "MessageUpdateEvent",
    "MessageEndEvent",
    "ToolExecutionStartEvent",
    "ToolExecutionUpdateEvent",
    "ToolExecutionEndEvent",
    # session-level events
    "QueueUpdateEvent",
    "CompactionStartEvent",
    "CompactionEndEvent",
    "AutoRetryStartEvent",
    "AutoRetryEndEvent",
    "SessionInfoChangedEvent",
    "ThinkingLevelChangedEvent",
]
