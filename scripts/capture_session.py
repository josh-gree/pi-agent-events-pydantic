"""Drive a LOCAL `pi --mode rpc` and capture its raw stdout JSONL to a file.

Produces a real session you can replay through the parser (scripts/check_session.py)
to prove full coverage. No E2B needed — this talks to the `pi` on your PATH.

    OPENROUTER_API_KEY=... python scripts/capture_session.py \
        --model openrouter/deepseek/deepseek-v4-flash \
        --out sessions/local.jsonl \
        "Create /tmp/pi-notes.txt with the text hello, then say what you did."

Why a harness and not interactive typing:
  * stdin in rpc mode is JSONL, not free text ({"type":"prompt","message":"..."}).
  * extension_ui_request must be answered or the agent blocks (file confirmations
    are on by default) — we auto-answer.
  * completion is `agent_end`, not EOF; we wait for it, then shut down cleanly.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="*", help="prompt(s); each runs to agent_end in order")
    ap.add_argument("--model", default="openrouter/deepseek/deepseek-v4-flash")
    ap.add_argument("--out", default="sessions/local.jsonl")
    ap.add_argument("--cwd", default="/tmp", help="working dir for the agent")
    ap.add_argument("--timeout", type=float, default=180.0, help="per-prompt seconds")
    args = ap.parse_args()

    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY missing", file=sys.stderr)
        return 2
    prompts = args.prompt or [
        "Create /tmp/pi-notes.txt containing the text 'hello typed world', "
        "then tell me in one sentence what you did."
    ]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # --no-extensions: skip extension discovery, so no extension_ui_request lines
    # (e.g. file-change confirmations) — nothing to auto-answer. The handler below
    # stays as a defensive no-op in case any slip through.
    proc = subprocess.Popen(
        ["pi", "--no-extensions", "--mode", "rpc", "--model", args.model],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=args.cwd,
        text=True,
        bufsize=1,
    )
    assert proc.stdin and proc.stdout and proc.stderr

    lines: list[str] = []
    agent_end = threading.Event()
    lock = threading.Lock()

    def send(obj: dict) -> None:
        with lock:
            proc.stdin.write(json.dumps(obj) + "\n")
            proc.stdin.flush()

    def reader() -> None:
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            lines.append(line)
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = msg.get("type")
            # auto-answer UI requests so the agent never blocks (footgun #5)
            if t == "extension_ui_request":
                method = msg.get("method")
                if method == "confirm":
                    send({"type": "extension_ui_response", "id": msg["id"], "confirmed": True})
                elif method == "select":
                    opts = msg.get("options") or [""]
                    send({"type": "extension_ui_response", "id": msg["id"], "value": opts[0]})
                elif method in ("input", "editor"):
                    send({"type": "extension_ui_response", "id": msg["id"], "value": ""})
                # notify/setStatus/setWidget/setTitle/set_editor_text need no reply
            elif t == "agent_end":
                agent_end.set()

    def stderr_reader() -> None:
        for raw in proc.stderr:
            sys.stderr.write("[pi stderr] " + raw)

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=stderr_reader, daemon=True).start()

    try:
        for i, p in enumerate(prompts, 1):
            print(f"→ prompt {i}/{len(prompts)}: {p}", file=sys.stderr)
            agent_end.clear()
            send({"type": "prompt", "message": p})
            if not agent_end.wait(timeout=args.timeout):
                print(f"! timed out waiting for agent_end on prompt {i}", file=sys.stderr)
                break
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    out_path.write_text("\n".join(lines) + "\n")
    print(f"captured {len(lines)} lines -> {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
