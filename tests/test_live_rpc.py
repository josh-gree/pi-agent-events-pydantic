"""Live integration: drive a real, multi-turn `pi --no-extensions --mode rpc`
session using only the generated classes, and assert the whole round trip parses.

Opt-in only — it spawns `pi`, makes real (paid, nondeterministic) model calls,
and needs pi's auth. It is skipped unless ``PI_RPC_LIVE=1`` and `pi` is on PATH.

    just test-live        # or: PI_RPC_LIVE=1 uv run pytest -m integration
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from collections import Counter

import pytest
from pydantic import ValidationError

from pi_agent_events import AgentSessionEvent, PromptCommand, PromptResponse
from pi_agent_events.models import AgentEndEvent, TextContent

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("PI_RPC_LIVE") != "1",
                       reason="set PI_RPC_LIVE=1 to run the live pi rpc drive test"),
    pytest.mark.skipif(shutil.which("pi") is None, reason="pi not on PATH"),
]


def _assistant_text(end: AgentEndEvent) -> str:
    """Last assistant message's text, via typed traversal of an agent_end."""
    text = ""
    for msg in end.messages:
        m = getattr(msg, "root", msg)
        if getattr(m, "role", None) == "assistant":
            text = "".join(c.text for c in m.content if isinstance(c, TextContent))
    return text


def _drive(messages: list[str], timeout_each: float = 150.0):
    """Send each prompt in turn over one persistent session, waiting for that
    turn's agent_end before the next. Returns (acks, texts, counts, failures),
    all parsed via the generated classes."""
    proc = subprocess.Popen(
        ["pi", "--no-extensions", "--mode", "rpc"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1,
    )
    assert proc.stdin and proc.stdout

    turn_done = threading.Event()
    acks: list[PromptResponse] = []
    texts: list[str] = []
    counts: Counter[str] = Counter()
    failures: list[str] = []

    def reader() -> None:
        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            obj = json.loads(line)
            try:
                if obj.get("type") == "response":
                    acks.append(PromptResponse.model_validate(obj))
                    continue
                evt = AgentSessionEvent.model_validate(obj).root
                counts[type(evt).__name__] += 1
                if isinstance(evt, AgentEndEvent):
                    texts.append(_assistant_text(evt))
                    turn_done.set()
            except ValidationError as e:
                failures.append(f"{obj.get('type')}: {e.errors(include_url=False)[:1]}")

    threading.Thread(target=reader, daemon=True).start()

    try:
        for i, msg in enumerate(messages, 1):
            turn_done.clear()
            cmd = PromptCommand(type="prompt", id=str(i), message=msg)
            proc.stdin.write(cmd.model_dump_json(exclude_none=True) + "\n")
            proc.stdin.flush()
            if not turn_done.wait(timeout=timeout_each):
                break
    finally:
        try:
            proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
    return acks, texts, counts, failures


def test_drive_multi_turn_live() -> None:
    acks, texts, counts, failures = _drive([
        "Remember this number: 7. Reply with just the word: ok.",
        "What number did I just ask you to remember? Reply with only the digit.",
    ])
    assert not failures, f"stdout lines failed to parse: {failures}"

    # two turns each ran to their own agent_end on the one persistent session
    assert counts["AgentEndEvent"] == 2
    assert counts["AgentStartEvent"] == 2

    # each prompt got its own ack, parsed as PromptResponse and correlated by id
    assert [a.id for a in acks] == ["1", "2"]
    assert all(a.command == "prompt" and a.success is True for a in acks)

    # real assistant content flowed for both turns, reachable via typed traversal
    assert len(texts) == 2 and all(t.strip() for t in texts)

    # the session carried context across turns: turn 2 recalls turn 1's number
    assert "7" in texts[1]
