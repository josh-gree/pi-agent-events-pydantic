"""Live integration: drive a real `pi --no-extensions --mode rpc` session using
only the generated classes, and assert the whole round trip parses.

Opt-in only — it spawns `pi`, makes a real (paid, nondeterministic) model call,
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


def _drive(message: str, timeout: float = 150.0):
    """Send one PromptCommand; parse every stdout line via the generated classes.
    Returns (reached_end, ack, counts, failures, final_text)."""
    proc = subprocess.Popen(
        ["pi", "--no-extensions", "--mode", "rpc"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1,
    )
    assert proc.stdin and proc.stdout

    done = threading.Event()
    counts: Counter[str] = Counter()
    failures: list[str] = []
    state: dict = {"ack": None, "text": None}

    def reader() -> None:
        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            obj = json.loads(line)
            try:
                if obj.get("type") == "response":
                    state["ack"] = PromptResponse.model_validate(obj)
                    continue
                evt = AgentSessionEvent.model_validate(obj).root
                counts[type(evt).__name__] += 1
                if isinstance(evt, AgentEndEvent):
                    for msg in evt.messages:
                        m = getattr(msg, "root", msg)
                        if getattr(m, "role", None) == "assistant":
                            state["text"] = "".join(
                                c.text for c in m.content if isinstance(c, TextContent)
                            )
                    done.set()
            except ValidationError as e:
                failures.append(f"{obj.get('type')}: {e.errors(include_url=False)[:1]}")

    threading.Thread(target=reader, daemon=True).start()

    cmd = PromptCommand(type="prompt", id="1", message=message)
    proc.stdin.write(cmd.model_dump_json(exclude_none=True) + "\n")
    proc.stdin.flush()

    reached = done.wait(timeout=timeout)
    try:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    return reached, state["ack"], counts, failures, state["text"]


def test_drive_and_parse_live() -> None:
    reached, ack, counts, failures, text = _drive(
        "Reply with exactly the word: pong. Do not use any tools."
    )
    assert not failures, f"stdout lines failed to parse: {failures}"
    assert reached, "never saw agent_end"
    # the prompt ack, parsed as PromptResponse and correlated by id
    assert ack is not None and ack.success is True
    assert ack.command == "prompt" and ack.id == "1"
    # the event stream parsed into typed events, terminating in exactly one agent_end
    assert counts["AgentStartEvent"] == 1
    assert counts["AgentEndEvent"] == 1
    assert counts["MessageUpdateEvent"] >= 1
    # real assistant content flowed and was reachable via typed traversal
    assert isinstance(text, str) and text.strip()
